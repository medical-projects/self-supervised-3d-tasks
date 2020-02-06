import csv
import gc
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas
from tensorflow.keras import backend as K
from sklearn.metrics import cohen_kappa_score

from self_supervised_3d_tasks.data.kaggle_retina_data import KaggleGenerator
from self_supervised_3d_tasks.keras_algorithms.custom_utils import init, apply_prediction_model
from self_supervised_3d_tasks.keras_algorithms.keras_train_algo import tensorflow.keras as keras_algorithm_list

epochs = 5
repetitions = 2
batch_size = 2
exp_splits = [100, 50, 25, 12.5, 6.25]  # different train splits to try in %

NGPUS = 1
lr = 0.00003

csvDescriptor_train = Path("/mnt/mpws2019cl1/kaggle_retina/train/trainLabels_shuffled_train.csv")
csvDescriptor_test = Path("/mnt/mpws2019cl1/kaggle_retina/train/trainLabels_shuffled_test.csv")


def score(y, y_pred):
    return "kappa score", cohen_kappa_score(y, y_pred, labels=[0, 1, 2, 3, 4], weights="quadratic")


def get_dataset_train(dataset_name, batch_size, f_train, f_val, train_split):
    if dataset_name == "kaggle_retina":
        gen_train = KaggleGenerator(batch_size=batch_size, sample_classes_uniform=True, shuffle=True,
                                    categorical=False, csvDescriptor=csvDescriptor_train, split=train_split,
                                    pre_proc_func_train=f_train, pre_proc_func_val=f_val)
    else:
        raise ValueError("not implemented")  # we can only test with kaggle retina atm.

    return gen_train


def get_dataset_test(dataset_name, batch_size, f_train, f_val):
    if dataset_name == "kaggle_retina":
        gen_test = KaggleGenerator(batch_size=batch_size, split=-1, shuffle=False, categorical=False,
                                   pre_proc_func_train=f_train, pre_proc_func_val=f_val,
                                   csvDescriptor=csvDescriptor_test)
        x_test, y_test = gen_test.get_val_data()
    else:
        raise ValueError("not implemented")  # we can only test with kaggle retina atm.

    return x_test, y_test


def run_single_test(algorithm_def, dataset_name, train_split, load_weights, freeze_weights, x_test, y_test):
    f_train, f_val = algorithm_def.get_finetuning_preprocessing()
    gen = get_dataset_train(dataset_name, batch_size, f_train, f_val, train_split)

    layer_in, x, cleanup_models = algorithm_def.get_finetuning_layers(load_weights, freeze_weights)
    model = apply_prediction_model(layer_in, x, multi_gpu=NGPUS, lr=lr)
    model.fit_generator(generator=gen, epochs=epochs)

    y_pred = model.predict(x_test)
    y_pred = np.rint(y_pred)
    s_name, result = score(y_test, y_pred)

    # cleanup
    del model
    for i in sorted(range(len(cleanup_models)), reverse=True):
        del cleanup_models[i]

    K.clear_session()

    for i in range(3):
        gc.collect()

    print("{} score: {}".format(s_name, result))
    return result


def write_result(base_path, row):
    with open(base_path + '_results.csv', 'a') as csvfile:
        result_writer = csv.writer(csvfile, delimiter=',')
        result_writer.writerow(row)


def draw_curve(name):
    # TODO: load multiple algorithms here
    # helper function to plot results curve
    df = pandas.read_csv(name + '_results.csv')

    plt.plot(df["Train Split"], df["Weights initialized"], label=name+' pretrained')
    plt.plot(df["Train Split"], df["Weights random"], label='Random')
    plt.plot(df["Train Split"], df["Weights freezed"], label=name+'Freezed')

    plt.legend()
    plt.show()

    print(df["Train Split"])


def run_complex_test(algorithm, dataset_name):
    results = []
    algorithm_def = keras_algorithm_list[algorithm]
    base_path = algorithm_def.model_checkpoint

    write_result(base_path, ["Train Split", "Weights freezed", "Weights initialized", "Weights random"])
    f_train, f_val = algorithm_def.get_finetuning_preprocessing()
    x_test, y_test = get_dataset_test(dataset_name, batch_size, f_train, f_val)

    for train_split in exp_splits:
        percentage = 0.01 * train_split
        print("running test for: {}%".format(train_split))

        a_s = []
        b_s = []
        c_s = []

        for i in range(repetitions):
            # load and freeze weights
            a = run_single_test(algorithm_def, dataset_name, percentage, True, True, x_test, y_test)

            # load weights and train
            b = run_single_test(algorithm_def, dataset_name, percentage, True, False, x_test, y_test)

            # random initialization
            c = run_single_test(algorithm_def, dataset_name, percentage, False, False, x_test, y_test)

            print("train split:{} model accuracy freezed: {}, initialized: {}, random: {}".format(percentage, a, b, c))

            a_s.append(a)
            b_s.append(b)
            c_s.append(c)

        data = [str(train_split) + "%", np.mean(np.array(a_s)), np.mean(np.array(b_s)), np.mean(np.array(c_s))]
        results.append(data)
        write_result(base_path, data)


if __name__ == "__main__":
    # draw_curve("jigsaw")
    init(run_complex_test, "test", NGPUS)
