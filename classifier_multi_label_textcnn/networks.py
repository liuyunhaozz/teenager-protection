# -*- coding: utf-8 -*-
"""
这段代码是一个使用ALBERT模型和TextCNN结构的文本分类网络的实现。它使用了TensorFlow框架，并结合了ALBERT模型和TextCNN模型的特点。

代码中定义了一个名为NetworkAlbertTextCNN的类，它接收一个布尔类型的参数is_training，用于指示当前是否处于训练模式。类的初始化方法中首先定义了输入数据的占位符，包括input_ids、input_masks、segment_ids和label_ids。然后通过调用modeling.AlbertModel类构造了ALBERT模型，并传入相应的参数。接着，将ALBERT模型的输出作为输入，调用cell_textcnn函数构建了TextCNN模型，得到TextCNN的输出output_layer。最后，将TextCNN的输出通过全连接层得到预测结果，并计算损失函数和优化器。
"""


import os
import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()
# import tensorflow as tf
import modeling
import optimization
from modules import cell_textcnn
from utils import time_now_string
from hyperparameters import Hyperparamters as hp
from classifier_utils import ClassifyProcessor

# use focal loss
import tensorflow_addons as tfa

num_labels = hp.num_labels
processor = ClassifyProcessor() 
bert_config_file = os.path.join(hp.bert_path,'albert_config.json')
bert_config = modeling.AlbertConfig.from_json_file(bert_config_file)


class NetworkAlbertTextCNN(object):
    def __init__(self,is_training):
        # Training or not
        self.is_training = is_training            
        # Placeholder       
        self.input_ids = tf.placeholder(tf.int32, shape=[None, hp.sequence_length], name='input_ids')
        self.input_masks = tf.placeholder(tf.int32, shape=[None,  hp.sequence_length], name='input_masks')
        self.segment_ids = tf.placeholder(tf.int32, shape=[None,  hp.sequence_length], name='segment_ids')
        self.label_ids = tf.placeholder(tf.float32, shape=[None,hp.num_labels], name='label_ids')               
        # Load BERT model
        self.model = modeling.AlbertModel(
                                    config=bert_config,
                                    is_training=self.is_training,
                                    input_ids=self.input_ids,
                                    input_mask=self.input_masks,
                                    token_type_ids=self.segment_ids,
                                    use_one_hot_embeddings=False)
        # Get the feature vector by BERT
        output_layer_init = self.model.get_sequence_output()      
        # Cell TextCNN
        output_layer = cell_textcnn(output_layer_init,self.is_training)
        # Hidden size 
        hidden_size = output_layer.shape[-1].value   
	# Full-connection
        with tf.name_scope("Full-connection"):  
            output_weights = tf.get_variable(
                  "output_weights", [num_labels, hidden_size],
                  initializer=tf.truncated_normal_initializer(stddev=0.02))            
            output_bias = tf.get_variable(
                  "output_bias", [num_labels], initializer=tf.zeros_initializer())   
            logits = tf.nn.bias_add(tf.matmul(output_layer, output_weights, transpose_b=True), output_bias)
            # Prediction sigmoid(Multi-label)
            self.probabilities = tf.nn.sigmoid(logits)
        with tf.variable_scope("Prediction"):             
            # Prediction               
            zero = tf.zeros_like(self.probabilities)
            one = tf.ones_like(self.probabilities)
            self.predictions = tf.where(self.probabilities < 0.5, x=zero, y=one)
        with tf.variable_scope("loss"):            
            # Summary for tensorboard
            if self.is_training:
	            self.accuracy = tf.reduce_mean(tf.to_float(tf.equal(self.predictions, self.label_ids)))
	            tf.summary.scalar('accuracy', self.accuracy) 
                                               
            # Initial embedding by BERT
            ckpt = tf.train.get_checkpoint_state(hp.saved_model_path)
            checkpoint_suffix = ".index"
            if ckpt and tf.gfile.Exists(ckpt.model_checkpoint_path + checkpoint_suffix):
                print('='*10,'Restoring model from checkpoint!','='*10)
                print("%s - Restoring model from checkpoint ~%s" % (time_now_string(),
                                                                    ckpt.model_checkpoint_path))
            else:                   
                print('='*10,'First time load BERT model!','='*10)
                tvars = tf.trainable_variables()
                if hp.init_checkpoint:
                   (assignment_map, initialized_variable_names) = \
                     modeling.get_assignment_map_from_checkpoint(tvars,
                                                                 hp.init_checkpoint)
                   tf.train.init_from_checkpoint(hp.init_checkpoint, assignment_map)
                                
            # Loss and Optimizer
            if self.is_training:
                # Global_step
                self.global_step = tf.Variable(0, name='global_step', trainable=False)                  
                per_example_loss = tf.nn.sigmoid_cross_entropy_with_logits(labels=self.label_ids,logits=logits)
                # per_example_loss = tfa.losses.sigmoid_focal_crossentropy(y_true=self.label_ids, y_pred=logits, alpha=0.25, gamma=2.0, from_logits=True) 
                self.loss = tf.reduce_mean(per_example_loss)              
                # Optimizer BERT
                train_examples = processor.get_train_examples(hp.data_dir)
                num_train_steps = int(
                    len(train_examples) / hp.batch_size * hp.num_train_epochs)
                num_warmup_steps = int(num_train_steps * hp.warmup_proportion)
                print('num_train_steps',num_train_steps)
                self.optimizer = optimization.create_optimizer(self.loss,
                                                                hp.learning_rate, 
                                                                num_train_steps, 
                                                                num_warmup_steps,
                                                                hp.use_tpu,
                                                                Global_step=self.global_step)    

                # Summary for tensorboard                 
                tf.summary.scalar('loss', self.loss)
                self.merged = tf.summary.merge_all()
                
                
                
if __name__ == '__main__':
    # Load model
    albert = NetworkAlbertTextCNN(is_training=True)




