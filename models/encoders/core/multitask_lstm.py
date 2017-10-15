#! /usr/bin/env python
# -*- coding: utf-8 -*-

"""Multi-task unidirectional LSTM encoder."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf


class MultitaskLSTMEncoder(object):
    """Multi-task unidirectional LSTM encoder.
    Args:
        num_units (int): the number of units in each layer
        num_layers_main (int): the number of layers of the main task
        num_layers_sub (int): the number of layers of the sub task
        lstm_impl (string): BasicLSTMCell or LSTMCell or
            LSTMBlockCell or LSTMBlockFusedCell or CudnnLSTM.
            Choose the background implementation of tensorflow.
            Default is LSTMBlockCell.
        use_peephole (bool): if True, use peephole
        parameter_init (float): the range of uniform distribution to
            initialize weight parameters (>= 0)
        clip_activation (float): the range of activation clipping (> 0)
        num_proj (int): the number of nodes in recurrent projection layer
        name (string, optional): the name of encoder
    """

    def __init__(self,
                 num_units,
                 num_layers_main,
                 num_layers_sub,
                 lstm_impl,
                 use_peephole,
                 parameter_init,
                 clip_activation,
                 num_proj,
                 name='multitask_lstm_encoder'):
        if num_proj == 0:
            raise ValueError

        self.num_units = num_units
        if lstm_impl != 'LSTMCell':
            self.num_proj = None
        # TODO: fix this
        self.num_layers_main = num_layers_main
        self.num_layers_sub = num_layers_sub
        self.lstm_impl = lstm_impl
        self.use_peephole = use_peephole
        self.parameter_init = parameter_init
        self.clip_activation = clip_activation
        self.name = name

        if self.num_layers_sub < 1 or self.num_layers_main < self.num_layers_sub:
            raise ValueError(
                'Set num_layers_sub between 1 to num_layers_main.')

    def __call__(self, inputs, inputs_seq_len, keep_prob):
        """Construct model graph.
        Args:
            inputs (placeholder): A tensor of size`[B, T, input_size]`
            inputs_seq_len (placeholder): A tensor of size` [B]`
            keep_prob (placeholder, float): A probability to keep nodes
                in the hidden-hidden connection
        Returns:
            outputs: A tensor of size `[T, B, input_size]` in the main task
            final_state: A final hidden state of the encoder in the main task
            outputs_sub: A tensor of size `[T, B, input_size]` in the sub task
            final_state_sub: A final hidden state of the encoder in the sub task
        """
        initializer = tf.random_uniform_initializer(
            minval=-self.parameter_init, maxval=self.parameter_init)

        # Hidden layers
        lstm_list = []
        with tf.variable_scope('multi_lstm', initializer=initializer) as scope_lstm:
            for i_layer in range(1, self.num_layers_main + 1, 1):

                if self.lstm_impl == 'BasicLSTMCell':
                    lstm = tf.contrib.rnn.BasicLSTMCell(
                        self.num_units,
                        forget_bias=1.0,
                        state_is_tuple=True,
                        activation=tf.tanh)

                elif self.lstm_impl == 'LSTMCell':
                    lstm = tf.contrib.rnn.LSTMCell(
                        self.num_units,
                        use_peepholes=self.use_peephole,
                        cell_clip=self.clip_activation,
                        num_proj=self.num_proj,
                        forget_bias=1.0,
                        state_is_tuple=True)

                elif self.lstm_impl == 'LSTMBlockCell':
                    # NOTE: This should be faster than tf.contrib.rnn.LSTMCell
                    lstm = tf.contrib.rnn.LSTMBlockCell(
                        self.num_units,
                        forget_bias=1.0,
                        # clip_cell=True,
                        use_peephole=self.use_peephole)
                    # TODO: cell clipping (update for rc1.3)

                elif self.lstm_impl == 'LSTMBlockFusedCell':
                    raise NotImplementedError

                elif self.lstm_impl == 'CudnnLSTM':
                    raise ValueError

                else:
                    raise IndexError(
                        'lstm_impl is "BasicLSTMCell" or "LSTMCell" or ' +
                        '"LSTMBlockCell" or "LSTMBlockFusedCell" or ' +
                        '"CudnnLSTM".')

                # Dropout for the hidden-hidden connections
                lstm = tf.contrib.rnn.DropoutWrapper(
                    lstm, output_keep_prob=keep_prob)

                lstm_list.append(lstm)

                if i_layer == self.num_layers_sub:
                    lstm_list_sub = lstm_list

            # Stack multiple cells
            stacked_lstm = tf.contrib.rnn.MultiRNNCell(
                lstm_list, state_is_tuple=True)

            # Ignore 2nd return (the last state)
            outputs, final_state = tf.nn.dynamic_rnn(
                cell=stacked_lstm,
                inputs=inputs,
                sequence_length=inputs_seq_len,
                dtype=tf.float32,
                scope=scope_lstm)
            # NOTE: initial states are zero states by default

        with tf.variable_scope('multi_lstm', initializer=initializer, reuse=True) as scope_lstm:
            # Stack multiple cells
            stacked_lstm_sub = tf.contrib.rnn.MultiRNNCell(
                lstm_list_sub, state_is_tuple=True)

            # Ignore 2nd return (the last state)
            outputs_sub, final_state_sub = tf.nn.dynamic_rnn(
                cell=stacked_lstm_sub,
                inputs=inputs,
                sequence_length=inputs_seq_len,
                dtype=tf.float32,
                scope=scope_lstm)

        return outputs, final_state, outputs_sub, final_state_sub
