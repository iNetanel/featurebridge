#!/bin/env python
'''
    Project Name: FeatureBridge
    Author: Netanel Eliav
    Author Email: inetanel@me.com
    License: MIT License
    Version: Please refer to the repository for the latest version and updates.
'''

# Import necessary libraries
import numpy as np
import pandas as pd
import copy, time
import matplotlib.pyplot as plt
from itertools import combinations
from featurebridge.utils import Utils, _convert_to_dataframe

# Define a class named FeatureBridge
class FeatureBridge:
    def __init__(self, model, correlation_threshold=0.3, min_accuracy=0.5, default_accuracy_selection=0.95, importance_threshold=0.1, accuracy_logic=None):
        """
        Initialize the main FeatureBridge object.

        Parameters:
            model (object): The machine learning model backbone (e.g., LinearRegression) to be used for modeling.
            correlation_threshold (float): The correlation threshold for feature selection based on correlation.
            min_accuracy (float): The minimum accuracy required for feature selection.
            default_accuracy_selection (float): The default accuracy threshold for feature selection.
            importance_threshold (float): The threshold for feature importance.
            accuracy_logic (function): Custom accuracy calculation logic (optional).

        Returns:
            None
        """

        self.utils = Utils()
        self.correlation_threshold = correlation_threshold
        self.min_accuracy = min_accuracy
        self.importance_threshold = importance_threshold
        self.default_accuracy_selection = default_accuracy_selection
        self.model = copy.deepcopy(model)  # Create a deep copy of the provided machine learning model
        self.accuracy_logic = accuracy_logic
        self.x_df = None  # Placeholder for feature data frame
        self.y_df = None  # Placeholder for target data frame
        self.feature_distribution = None  # Placeholder for feature distribution statistics
        self.feature_importance = None  # Placeholder for basic feature importance
        self.corr_matrix = None  # Placeholder for the correlation matrix
        self.max_feature = None  # Placeholder for the most important feature
        self.max_index = None  # Placeholder for the index of the maximum feature importance
        self.model_map = None  # Placeholder for a mapping of features and models
        self.training_time = None

    # Define a custom exception class
    class MandatoryFeatureError(Exception):
        pass
    
    # Define a string representation for the class
    def __str__(self):
        """
        Define the string representation of the object.

        Returns:
            FeatureBridge internal information
        """
        message = f'''
        FeatureBridge Class:
         - Parameters:
            - Model (Backbone) = {self.model.__class__.__name__}
            - Correlation Threshold = {self.correlation_threshold}
            - Minimum Accuracy = {self.min_accuracy}
            - Default Accuracy Selection = {self.default_accuracy_selection}
            - Importance Threshold = {self.importance_threshold}
            - Accuracy Logic = {self.accuracy_logic}
         - Model:
            - Trained = {self.model_map is not None}
            - Training UTC Time = {self.training_time}
         '''

        return message

    # Method to fit the model to the data
    def fit(self, x_df, y_df):
        """
        Fit the machine learning model to the input data.

        Parameters:
            x_df (DataFrame): The feature data frame.
            y_df (Series or array-like): The target variable data.

        Returns:
            None
        """
        x_df = _convert_to_dataframe(x_df, 'dataframe') # Validate data type and convert it to pandas dataframe if needed.
        y_df = _convert_to_dataframe(y_df, 'series') # Validate data type and convert it to pandas dataframe if needed.

        self.model = self.model.fit(x_df, y_df)
        self.x_df = x_df  # Assign the feature data frame
        self.y_df = y_df  # Assign the target data frame
        self.feature_distribution = self._distribution()  # Calculate feature distribution statistics
        self.feature_importance = self._calculate_importance()  # Calculate basic feature importance
        self.corr_matrix = self.x_df.corr()  # Calculate the correlation matrix
        self.max_feature = self.feature_importance.max()  # Find the most important feature
        self.max_index = self.feature_importance.idxmax()  # Find the index of the maximum feature importance
        self.model_map, self.training_time = self._model_mapping()  # Create a mapping of features and models
        self._feature_mapping()

    # Method to make predictions
    def predict(self, x_df):
        """
        Make predictions using the fitted model.

        Parameters:
            x_df (DataFrame): The feature data frame for prediction.

        Returns:
            array: Predicted values.
        """

        x_df = self.df_bridge(x_df)
        return self.model.predict(x_df)

    def _get_model_coefficients(self):
        """
        Get coefficients or feature importances from a scikit-learn model.

        Parameters:
        - model: A trained scikit-learn model.
        - feature_names: List of feature names (column names) for the input data.

        Returns:
        - Coefficients or feature importances.
        """

        if hasattr(self.model, 'coef_'):
            # Linear models (Linear Regression, Logistic Regression, Linear SVM)
            coefficients = self.model.coef_
            return coefficients.ravel()
        if hasattr(self.model, 'feature_importances_'):
            # Tree-based models (Random Forest, Decision Tree)
            feature_importances = self.model.feature_importances_
            return feature_importances.ravel()

        raise ValueError(f"Model type {type(self.model)} not recognized or supported.")
    
    # Method to calculate feature importance
    def _calculate_importance(self):
        """
        Calculate the basic feature importance.

        Returns:
            Series: Feature importances.
        """

        # Create a new Series with the same columns as the original DataFrame
        im_df = pd.Series('', index=self.x_df.columns)
        for index_name in im_df.index:
            # Use the data distribution to have better feature importance
            im_df.at[index_name] = self.feature_distribution[index_name][2]

        return np.abs(self._get_model_coefficients() * im_df)

    # Method to print feature importance scores
    def feature_importance_score(self):
        """
        Summarize feature importance scores.

        Returns:
            None
        """

        features_list = self.x_df.columns
        for i, v in enumerate(self.feature_importance):
            print('Feature: %s (%0d), Score: %.5f' % (features_list[i], i, v))

    # Method to determine feature distribution characteristics
    def _distribution(self):
        """
        Determine the method for handling feature distribution based on data characteristics.

        Returns:
            dict: Mapping of features to distribution methods.
        """

        feature_distribution = {}
        for feature in self.x_df.columns:
            # Check if data is binary (0 or 1)
            feature_distribution[feature] = self.utils._fit_distribution(self.x_df[feature])

        return feature_distribution

    # Method to identify features to drop based on correlation
    def _drop_matrix(self, feature):
        """
        Identify features to drop based on correlation with the specified feature.

        Parameters:
            feature (str): The target feature.

        Returns:
            list: List of features to drop.
        """

        matrix = np.abs(self.corr_matrix)
        criteria1 = matrix < self.correlation_threshold
        criteria2 = matrix == 1
        cleared_matrix = matrix[criteria1 | criteria2]
        drop_matrix = cleared_matrix[feature]
        drop_matrix = drop_matrix.dropna()
        return drop_matrix.index.tolist()

    # Method to generate all combinations of features
    def _all_combinations(self, x_df):
        """
        Generate all possible combinations of features.

        Parameters:
            x_df (DataFrame): The feature data frame.

        Returns:
            list: List of feature combinations.
        """

        all_combinations = []
        for r in range(1, len(x_df) + 1):
            comb_r = list(combinations(x_df, r))
            all_combinations.extend(comb_r)
        return all_combinations

    # Method to create a mapping of models for each feature
    def _model_mapping(self):
        """
        Map models to features based on accuracy.

        Returns:
            dict: Mapping of features to models and accuracy.
            timestamp: the last time .fit method was executed (aka training).
        """

        model = copy.deepcopy(self.model)
        model_map = {}
        for feature in self.x_df.columns:
            x_df = self.x_df.drop(self._drop_matrix(feature), axis=1)
            y_df = self.x_df[feature].values.reshape(-1, 1)
            i = 0
            if len(x_df.columns) == 0:
                model_map[feature] = {i: {'accuracy': None, 'distribution': self.feature_distribution[feature], 'features': None, 'model': None}}
                continue
            model_map[feature] = {i: {'accuracy': None, 'distribution': self.feature_distribution[feature], 'features': None, 'model': None}}
            combinations = self._all_combinations(x_df)
            for combination in combinations:
                combination = list(combination)
                if len(combination) != len(x_df.columns):
                    x_df_droped = x_df.drop(combination, axis=1)
                else:
                    break
                model.fit(x_df_droped, y_df)
                ypred = model.predict(x_df_droped)
                acc = 1 - self.accuracy(y_df, ypred)
                if acc < self.min_accuracy:
                    if len(model_map[feature]) < 1:
                        del model_map[feature][i]
                else:
                    model_map[feature][i] = {'accuracy': acc, 'distribution': self.feature_distribution[feature], 'features': list(x_df_droped.columns), 'model': copy.deepcopy(model)}
                    if acc >= self.default_accuracy_selection:
                        break
                i += 1
        

        # Set time and format the UTC time as a string
        formatted_utc_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time()))
        return model_map, formatted_utc_time

    # Method to identify mandatory and deviation features
    def _mandatory_and_distribution(self):
        """
        Identify mandatory and deviation features based on importance.

        Returns:
            None
        """

        for feature in self.model_map:
            for i in self.model_map[feature]:
                if self.model_map[feature][i]['features'] is None:
                    if (self.feature_importance[feature] / (np.sum(self.feature_importance, axis=0))) > self.importance_threshold:
                        self.feature_map['mandatory'][feature] = self.model_map[feature][i]
                    else:
                        self.feature_map['deviation'][feature] = self.model_map[feature][i]

        for feature in self.feature_map['mandatory']:
            del self.model_map[feature]
        for feature in self.feature_map['deviation']:
            del self.model_map[feature]

    # Method to build the adaptive model
    def _adaptive_model(self):
        """
        Perform the build of adaptive model for feature prediction based on dependencies.

        Returns:
            None
        """

        while len(self.model_map) > 0:
            model_map_l1 = {}
            for feature in self.model_map:
                found_keys = list(self.feature_map['mandatory'].keys()) + list(self.feature_map['deviation'].keys()) + list(self.feature_map['adaptive'].keys())
                if len(found_keys) > 0:
                    for i in self.model_map[feature]:
                        found_in_keys = [item in self.model_map[feature][i]['features'] for item in found_keys]
                        if found_in_keys and found_in_keys.count(True) == len(self.model_map[feature][i]['features']):
                            if feature in model_map_l1:
                                if model_map_l1[feature]['accuracy'] < self.model_map[feature][i]['accuracy']:
                                    model_map_l1[feature] = self.model_map[feature][i]
                            else:
                                model_map_l1[feature] = self.model_map[feature][i]
            if not model_map_l1:
                for feature in self.model_map:
                    for i in self.model_map[feature]:
                        if feature in model_map_l1:
                            if model_map_l1[feature]['accuracy'] < self.model_map[feature][i]['accuracy']:
                                model_map_l1[feature] = self.model_map[feature][i]
                        else:
                            model_map_l1[feature] = self.model_map[feature][i]

                if model_map_l1:
                    model_map_l1_sorted = dict(sorted(model_map_l1.items(), key=lambda item: item[1]['accuracy'], reverse=False))
                    if (self.feature_importance[next(iter(model_map_l1_sorted))]/(np.sum(self.feature_importance, axis=0))) > self.importance_threshold:
                        self.feature_map['mandatory'][next(iter(model_map_l1_sorted))] = model_map_l1_sorted[next(iter(model_map_l1_sorted))]
                        del self.model_map[next(iter(model_map_l1_sorted))]
                    else:
                        self.feature_map['deviation'][next(iter(model_map_l1_sorted))] = model_map_l1_sorted[next(iter(model_map_l1_sorted))]
                        del self.model_map[next(iter(model_map_l1_sorted))]
                    model_map_l1 = {}
            if model_map_l1:
                model_map_l1_sorted = dict(sorted(model_map_l1.items(), key=lambda item: item[1]['accuracy'], reverse=True))
                self.feature_map['adaptive'][next(iter(model_map_l1_sorted))] = model_map_l1_sorted[next(iter(model_map_l1_sorted))]
                del self.model_map[next(iter(model_map_l1_sorted))]

    # Method to print the feature mapping
    def feature_sequence(self):
        """
        Display feature sequence selection and their handling methods.

        Returns:
            None
        """

        print('Feature Sequence Dependencies:')
        print('Mandatory: (Must be provided by the user)')
        if len(self.feature_map['mandatory']) == 0:
            print(' - None')
        else:
            for i in self.feature_map['mandatory']:
                print(f' - Feature {i}')
        print('\nData Distribution Method: (data distribution method will be used and not prediction)')
        if len(self.feature_map['deviation']) == 0:
            print(' - None')
        else:
            for i in self.feature_map['deviation']:
                print(' - Feature {}, {}'.format(i, self.feature_map['deviation'][i]['distribution']))
        print('\nPrediction by Adaptive Model: (will be predict by adaptiv model)')
        if len(self.feature_map['adaptive']) == 0:
            print(' - None')
        else:
            for i in self.feature_map['adaptive']:
                print(' - Feature {}, Dependencies: {}'.format(i, self.feature_map['adaptive'][i]['features']))
        print('\n')

    def _feature_mapping(self):
        """
        Perform feature mapping and selection.

        Returns:
            None
        """

        self.feature_map = {'mandatory': {},
                            'deviation': {},
                            'adaptive': {},
                            }
        self._mandatory_and_distribution()
        self._adaptive_model()

    # Method to calculate prediction accuracy
    def accuracy(self, y_df, ypred):
        """
        Calculate prediction accuracy.

        Parameters:
            y_df (Series or array-like): The true target variable values.
            ypred (array): The predicted target variable values.

        Returns:
            float: Prediction accuracy.
        """

        if self.accuracy_logic is None:
            y_sum = np.sum(y_df)
            margin = np.abs(np.subtract(ypred, y_df))
            error_sum = np.sum(margin)
            accu = error_sum / y_sum
            if accu < 0:
                accu = 0
            if accu > 1:
                accu = 1
        else:
            accu = self.accuracy_logic(y_df, ypred)
        return accu

    # Method to predict using the adaptive model
    def _adaptive_predict(self, x_df, feature):
        """
        Make adaptive predictions for a specific feature.

        Parameters:
            x_df (DataFrame): The feature data frame.
            feature (str): The target feature.

        Returns:
            array: Predicted values for the specified feature.
        """

        if len(x_df.shape) == 1:
            x_df = x_df.values.reshape(-1, 1)
        else:
            x_df = pd.DataFrame(x_df)
        prediction = self.feature_map['adaptive'][feature]['model'].predict(x_df)
        return prediction.flatten().astype(float)

    # Method to prepare the input data frame for prediction
    def df_bridge(self, x_df):
        """
        Prepare the input data frame for prediction.

        Parameters:
            x_df (DataFrame): The feature data frame.

        Returns:
            DataFrame: Prepared feature data frame for prediction.
        """

        for feature in self.feature_map['mandatory']:
            if feature not in x_df.columns:
                raise self.MandatoryFeatureError("A mandatory feature is completely missing: {}".format(feature))
            else:
                if x_df[feature].isna().any().any():
                    raise self.MandatoryFeatureError("A mandatory feature is partially missing: {} > (please check for NaN values in your dataset)".format(feature))

        # Handling of data distribution method
        for feature in self.feature_map['deviation']:
            if feature not in x_df.columns:
                x_df[feature] = self.feature_map['deviation'][feature]['distribution'][2]
            if x_df[feature].isna().any().any():
                x_df[feature] = x_df[feature].fillna(self.feature_map['deviation'][feature]['distribution'][2])

        # Handling missing features with adaptive prediction
        for feature in self.feature_map['adaptive']:
            if feature not in x_df.columns:
                x_df[feature] = self._adaptive_predict(x_df[self.feature_map['adaptive'][feature]['features']], feature)
            if x_df[feature].isna().any().any():
                # pass  # TODO: Allow partial missing values for these features.
                mask = x_df[feature].isna()
                x_df.loc[mask, feature] = self._adaptive_predict(x_df.loc[mask][self.feature_map['adaptive'][feature]['features']], feature)
                
        # Reorder columns to match the original data frame
        x_df = x_df.reindex(columns=self.x_df.columns)
        return x_df
    
    # Method to benchmark the model
    def benchmark(self, x_test_df, y_text_df):
        """
        Evaluate the model's performance and impact of feature selection.

        Parameters:
            x_test_df (DataFrame): The feature data frame.
            y_text_df (DataFrame): The target data frame.

        Returns:
            None
        """
        
        model = copy.deepcopy(self.model)
        ypred = model.predict(x_test_df)
        main_acc = 1 - self.accuracy(y_text_df, ypred)
        print('Non-FeatureBridge Model Accuracy: {}\n'.format(main_acc))

        acc_results = []
        test_results = []
        test_results.append(ypred)

        for feature in (list(self.feature_map['deviation'].keys()) + list(self.feature_map['adaptive'].keys())):
            xtest_x = x_test_df.drop(feature, axis=1)
            ypred = self.predict(xtest_x)
            test_results.append(ypred)
            acc = 1 - self.accuracy(y_text_df, ypred)
            acc_results.append(acc)

        results = main_acc - acc_results
        modified_results = [0 if x < 0 else x for x in results]

        print("FeatureBridge feature accuracy impact:\nThis shows the impact of each feature when it's missing\n(Higher % number means higher impact in %)")
        features = (list(self.feature_map['deviation'].keys()) + list(self.feature_map['adaptive'].keys()))
        plt.figure(figsize=(len(self.feature_map)*3, 6))  # Adjust the width and height as needed
        plt.bar(features, (modified_results))
        plt.xlabel('Feature Name')
        plt.ylabel('Accuracy Impact')
        plt.title('Features and their accuracy impact in %')
        plt.show()

        print("FeatureBridge Performance Matrix:\nThis shows the performance of FeatureBridge, the average accuracy for every number of features missing.\n---")
        acc_results = []
        test_results = []
        all_combinations = []
        list_combinations = []
        main_accuracy = []
        base_f = (list(self.feature_map['deviation'].keys()) + list(self.feature_map['adaptive'].keys()))
        for r in range(1, len(base_f)):
            acc_results = []
            test_results = []
            all_combinations = []
            list_combinations = []
            all_combinations = combinations(base_f, r)
            for comb in list(all_combinations):
                list_combinations.append(list(comb))
            for feature in list_combinations:
                xtest_x = x_test_df.drop(feature, axis=1)
                ypred = self.predict(xtest_x)
                test_results.append(ypred)
                acc = 1 - self.accuracy(y_text_df, ypred)
                acc_results.append(acc)
            avg = sum(acc_results) / len(acc_results)
            main_accuracy.append(avg)
            print('Average FeatureBridge accuracy with {} missing features: {}'.format(r, avg))

        x_bx = range(1, len(main_accuracy) + 1)
        plt.figure(figsize=(len(self.feature_map)*3, 6))  # Adjust the width and height as needed
        plt.plot(x_bx, main_accuracy, linewidth=1, label='accuracy')
        plt.title("accuracy by number of missing features")
        plt.xlabel('Number of missing features')
        plt.ylabel('Accuracy')
        plt.legend(loc='best', fancybox=True, shadow=True)
        plt.grid(True)
        plt.show()
