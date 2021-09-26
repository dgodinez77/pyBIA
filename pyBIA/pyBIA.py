#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Sep 16 22:40:39 2021

@author: daniel
"""
from data_processing import process_class, create_training_set

def pyBIA_model(blob_data, other_data, img_num_channels=1):
    """
    The CNN model infrastructure presented by AlexNet, with
    modern modifications
    """
    if len(blob_data.shape) == 3:
        img_width = blob_data[0].shape[0]
        img_height = blob_data[0].shape[1]

    elif len(blob_data.shape) == 2:
        img_width = blob_data.shape[0]
        img_height = blob_data.shape[1]

    X_train, Y_train = create_training_set(blob_data, other_data)
    input_shape = (img_width, img_height, img_num_channels)

    epochs=100
    batch_size=64
    lr=0.0001
    momentum=0.9
    decay=0.0
    nesterov=False
    loss='categorical_crossentropy'
   
    # Uniform scaling initializer
    num_classes = 2
    uniform_scaling = VarianceScaling(
        scale=1.0, mode='fan_in', distribution='uniform', seed=None)

    # Model configuration
    model = Sequential()

    model.add(Conv2D(96, 11, strides=4, activation='relu', input_shape=input_shape,
                     padding='same', kernel_initializer=uniform_scaling))
    model.add(MaxPool2D(pool_size=3, strides=2, padding='same'))
    model.add(BatchNormalization())

    model.add(Conv2D(256, 5, activation='relu', padding='same',
                     kernel_initializer=uniform_scaling))
    model.add(MaxPool2D(pool_size=3, strides=2, padding='same'))
    model.add(BatchNormalization())

    model.add(Conv2D(384, 3, activation='relu', padding='same',
                     kernel_initializer=uniform_scaling))
    model.add(Conv2D(384, 3, activation='relu', padding='same',
                     kernel_initializer=uniform_scaling))
    model.add(Conv2D(256, 3, activation='relu', padding='same',
                     kernel_initializer=uniform_scaling))
    model.add(MaxPool2D(pool_size=3, strides=2, padding='same'))
    model.add(BatchNormalization())

    model.add(Flatten())
    model.add(Dense(4096, activation='tanh',
                    kernel_initializer='TruncatedNormal'))
    model.add(Dropout(0.5))
    model.add(Dense(4096, activation='tanh',
                    kernel_initializer='TruncatedNormal'))
    model.add(Dropout(0.5))
    model.add(Dense(num_classes, activation='softmax',
                    kernel_initializer='TruncatedNormal'))

    optimizer = optimizers.SGD(lr=lr, momentum=momentum,
                         decay=decay, nesterov=nesterov)
    model.compile(loss=loss, optimizer=optimizer, metrics=['accuracy'])
    model.fit(X_train, Y_train, batch_size=batch_size, epochs=no_epochs, verbose=1)

    return model


def predict(data, model):
    """
    Returns class prediction
    """
    data = process_class(data)
    pred = model.predict(data)

    return pred
