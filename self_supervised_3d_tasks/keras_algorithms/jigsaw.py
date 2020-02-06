from os.path import expanduser

from tensorflow.keras import Input, Model
from tensorflow.keras.layers import TimeDistributed, Flatten
from tensorflow.keras.optimizers import Adam

from self_supervised_3d_tasks.custom_preprocessing.jigsaw_preprocess import preprocess, preprocess_resize
from self_supervised_3d_tasks.keras_algorithms.custom_utils import apply_encoder_model, apply_encoder_model_3d, \
    load_permutations, load_permutations_3d
from self_supervised_3d_tasks.keras_models.fully_connected import fully_connected

h_w = 384
split_per_side = 3
n_patches = split_per_side * split_per_side
n_patches3D = split_per_side * split_per_side * split_per_side
dim = (h_w, h_w)
dim3D = (h_w, h_w, h_w)
patch_jitter = 10
patch_dim = int((h_w / split_per_side) - patch_jitter)
n_channels = 3
lr = 0.00003  # choose a smaller learning rate
embed_dim = 1000
architecture = "ResNet50"
# data_dir="/mnt/mpws2019cl1/retinal_fundus/left/max_256/"
model_checkpoint = \
    expanduser('~/workspace/self-supervised-transfer-learning/jigsaw_kaggle_retina_3/weights-improvement-059.hdf5')
train3d = True


def apply_model():
    if train3d:
        perms, _ = load_permutations_3d()
    else:
        perms, _ = load_permutations()

    if train3d:
        input_x = Input((n_patches3D, patch_dim, patch_dim, patch_dim, n_channels))
        enc_model = apply_encoder_model_3d((patch_dim, patch_dim, patch_dim, n_channels, ), embed_dim)
    else:
        input_x = Input((n_patches, patch_dim, patch_dim, n_channels))
        enc_model = apply_encoder_model((patch_dim, patch_dim, n_channels, ), embed_dim)

    x = TimeDistributed(enc_model)(input_x)
    x = Flatten()(x)
    out = fully_connected(x, num_classes=len(perms))

    model = Model(inputs=input_x, outputs=out)
    model.compile(optimizer=Adam(lr=lr),
                  loss='categorical_crossentropy',
                  metrics=['accuracy'])
    model.summary()

    return enc_model, model


def get_training_model():
    return apply_model()[1]


def get_training_preprocessing():
    if train3d:
        perms, _ = load_permutations_3d()
    else:
        perms, _ = load_permutations()

    def f_train(x, y):  # not using y here, as it gets generated
        return preprocess(x, split_per_side, patch_jitter, perms, is_training=True, mode3d=train3d)

    def f_val(x, y):
        return preprocess(x, split_per_side, patch_jitter, perms, is_training=False, mode3d=train3d)

    return f_train, f_val


def get_finetuning_preprocessing():
    def f_train(x, y):
        return preprocess_resize(x, split_per_side, patch_dim, mode3d=train3d), y

    def f_val(x, y):
        return preprocess_resize(x, split_per_side, patch_dim, mode3d=train3d), y

    return f_train, f_val


def get_finetuning_layers(load_weights, freeze_weights):
    enc_model, model_full = apply_model()

    if load_weights:
        model_full.load_weights(model_checkpoint)

    if freeze_weights:
        # freeze the encoder weights
        enc_model.trainable = False

    layer_in = Input((split_per_side * split_per_side, patch_dim, patch_dim, n_channels))
    layer_out = TimeDistributed(enc_model)(layer_in)

    x = Flatten()(layer_out)
    return layer_in, x, [enc_model, model_full]
