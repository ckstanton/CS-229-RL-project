import tensorflow as tf
import numpy as np
from tensorflow.python.framework import ops
import time











class PolicyGradient:
    def __init__(
        self,
        n_x,
        n_y,
        learning_rate=0.01,
        reward_decay=0.95,
        load_path=None,
        save_path=None        
    ):

        self.n_x = n_x
        self.n_y = n_y
        self.lr = learning_rate
        self.gamma = reward_decay

        self.save_path = None
        if save_path is not None:
            self.save_path = save_path

        self.episode_observations, self.episode_actions, self.episode_rewards = [], [], []

        self.build_network()

        self.cost_history = []

        self.sess = tf.Session()

        

        # $ tensorboard --logdir=logs
        # http://0.0.0.0:6006/
        tf.summary.FileWriter("logs/", self.sess.graph)
        

        self.sess.run(tf.global_variables_initializer())

        # 'Saver' op to save and restore all the variables
        self.saver = tf.train.Saver()

        # Restore model
        if load_path is not None:
            self.load_path = load_path
            self.saver.restore(self.sess, self.load_path)

    def store_transition(self, s, a, r):
        """
            Store play memory for training
            Arguments:
                s: observation
                a: action taken
                r: reward after action
        """
        self.episode_observations.append(s)
        self.episode_rewards.append(r)

        # Store actions as list of arrays
        # e.g. for n_y = 2 -> [ array([ 1.,  0.]), array([ 0.,  1.]), array([ 0.,  1.]), array([ 1.,  0.]) ]
        action = np.zeros(self.n_y)
        action[a] = 1
        self.episode_actions.append(action)


    def choose_action(self, observation):
        """
            Choose action based on observation
            Arguments:
                observation: array of state, has shape (num_features)
            Returns: index of action we want to choose
        """
        # Reshape observation to (num_features, 1)
        observation = observation[:, np.newaxis]

        # Run forward propagation to get softmax probabilities
        prob_weights = self.sess.run(self.outputs_softmax, feed_dict = {self.X: observation})

        # Select action using a biased sample
        # this will return the index of the action we've sampled
        action = np.random.choice(range(len(prob_weights.ravel())), p=prob_weights.ravel())
        return action

    def learn(self):
        # Discount and normalize episode reward
        discounted_episode_rewards_norm = self.discount_and_norm_rewards()

        # Train on episode
        self.sess.run(self.train_op,  feed_dict={
             self.X: np.vstack(self.episode_observations).T,
             self.Y: np.vstack(np.array(self.episode_actions)).T,
             self.discounted_episode_rewards_norm: discounted_episode_rewards_norm,
        })

        # silly way of implementing tensorboard.. very slow
        #loss_summary = self.sess.run(self.loss_summary,  feed_dict={
        #     self.X: np.vstack(self.episode_observations).T,
        #     self.Y: np.vstack(np.array(self.episode_actions)).T,
        #     self.discounted_episode_rewards_norm: discounted_episode_rewards_norm,
        #})

        #tf.summary.FileWriter("logs/").add_summary(loss_summary)

        # Reset the episode data
        self.episode_observations, self.episode_actions, self.episode_rewards  = [], [], []

        # Save checkpoint
        if self.save_path is not None:
            save_path = self.saver.save(self.sess, self.save_path)
            print("Model saved in file: %s" % save_path)

        return discounted_episode_rewards_norm

    def discount_and_norm_rewards(self):
        discounted_episode_rewards = np.zeros_like(self.episode_rewards)
        cumulative = 0
        for t in reversed(range(len(self.episode_rewards))):
            cumulative = cumulative * self.gamma + self.episode_rewards[t]
            discounted_episode_rewards[t] = cumulative

        discounted_episode_rewards -= np.mean(discounted_episode_rewards)
        discounted_episode_rewards /= np.std(discounted_episode_rewards)
        
        return discounted_episode_rewards


    def build_network(self):
        # Create placeholders
        with tf.name_scope('inputs'):
            self.X = tf.placeholder(tf.float32, shape=(self.n_x, None), name="X")
            self.Y = tf.placeholder(tf.float32, shape=(self.n_y, None), name="Y")
            self.discounted_episode_rewards_norm = tf.placeholder(tf.float32, [None, ], name="actions_value")

        # Initialize parameters
        units_layer_1 = 10
        units_layer_2 = 10
        units_output_layer = self.n_y
        with tf.name_scope('parameters'):
            W1 = tf.get_variable("W1", [units_layer_1, self.n_x], initializer = tf.contrib.layers.xavier_initializer(seed=1))
            b1 = tf.get_variable("b1", [units_layer_1, 1], initializer = tf.contrib.layers.xavier_initializer(seed=1))
            W2 = tf.get_variable("W2", [units_layer_2, units_layer_1], initializer = tf.contrib.layers.xavier_initializer(seed=1))
            b2 = tf.get_variable("b2", [units_layer_2, 1], initializer = tf.contrib.layers.xavier_initializer(seed=1))
            W3 = tf.get_variable("W3", [self.n_y, units_layer_2], initializer = tf.contrib.layers.xavier_initializer(seed=1))
            b3 = tf.get_variable("b3", [self.n_y, 1], initializer = tf.contrib.layers.xavier_initializer(seed=1))

        # Forward prop
        with tf.name_scope('layer_1'):
            Z1 = tf.add(tf.matmul(W1,self.X), b1)
            A1 = tf.nn.relu(Z1)
        with tf.name_scope('layer_2'):
            Z2 = tf.add(tf.matmul(W2, A1), b2)
            A2 = tf.nn.relu(Z2)
        with tf.name_scope('layer_3'):
            Z3 = tf.add(tf.matmul(W3, A2), b3)
            A3 = tf.nn.softmax(Z3)

        # Softmax outputs, we need to transpose as tensorflow nn functions expects them in this shape
        logits = tf.transpose(Z3)
        labels = tf.transpose(self.Y)
        self.outputs_softmax = tf.nn.softmax(logits, name='A3')

        with tf.name_scope('loss'):
            neg_log_prob = tf.nn.softmax_cross_entropy_with_logits_v2(logits=logits, labels=labels)
            loss = tf.reduce_mean(neg_log_prob * self.discounted_episode_rewards_norm)  # reward guided loss
        
        #self.loss_summary=tf.summary.scalar('loss', loss)
        
        

        with tf.name_scope('train'):
            self.train_op = tf.train.AdamOptimizer(self.lr).minimize(loss)

    def plot_cost(self):
        import matplotlib
        #matplotlib.use("MacOSX")
        import matplotlib.pyplot as plt
        plt.plot(np.arange(len(self.cost_history)), self.cost_history)
        plt.ylabel('Cost')
        plt.xlabel('Training Steps')
        plt.show()


##########################################################################################################
##########################################################################################################
##########################################################################################################
##########################################################################################################
##########################################################################################################
##########################################################################################################

##########################################################################################################


###with experience replay sampling form the past 1000 frames.

class DeepQNetwork:
    def __init__(
        self,
        n_y,
        n_x,
        learning_rate=0.01,
        replace_target_iter=100,
        memory_size=1000,
        epsilon_max=0.9,
        epsilon_greedy_increment=0.001,
        batch_size=32,
        reward_decay=0.9,
        load_path=None,
        save_path=None
    ):

        self.n_y = n_y
        self.n_x = n_x
        self.lr = learning_rate
        self.epsilon_max = epsilon_max
        self.replace_target_iter = replace_target_iter
        self.memory_size = memory_size
        self.epsilon_greedy_increment = epsilon_greedy_increment
        self.batch_size = batch_size
        self.reward_decay = reward_decay # this is gamma
        self.save_path=save_path

        if save_path is not None:
            self.save_path = save_path

        self.memory_counter = 0
        self.learn_step_counter = 0

        if epsilon_greedy_increment is not None:
            self.epsilon = 0
        else:
            self.epsilon = self.epsilon_max

        # Initialize memory
        self.memory_s = np.zeros((n_x,self.memory_size))
        self.memory_a = np.zeros((self.memory_size))
        self.memory_r = np.zeros((self.memory_size))
        self.memory_s_ = np.zeros((n_x,self.memory_size))

        # Config for networks
        n_l1 = 10
        n_l2 = 10
        W_init = tf.contrib.layers.xavier_initializer(seed=1)
        b_init = tf.contrib.layers.xavier_initializer(seed=1)
        self.build_eval_network(n_l1, n_l2, W_init, b_init)
        self.build_target_network(n_l1, n_l2, W_init, b_init)

        self.sess = tf.Session()

        self.cost_history = []

        # $ tensorboard --logdir=logs
        # http://0.0.0.0:6006/
        tf.summary.FileWriter("logs/", self.sess.graph)

        init = tf.global_variables_initializer()
        self.sess.run(init)

        # 'Saver' op to save and restore all the variables
        self.saver = tf.train.Saver()

        # Restore model
        if load_path is not None:
            self.load_path = load_path
            self.saver.restore(self.sess, self.load_path)

    def store_transition(self, s, a, r, s_):
        # Replace old memory with new memory
        index = self.memory_counter % self.memory_size

        self.memory_s[:,index] = s
        self.memory_a[index] = a
        self.memory_r[index] = r
        self.memory_s_[:,index] = s_

        self.memory_counter += 1

    def choose_action(self, observation):
        # Reshape to (num_features, 1)
        observation = observation[ :,np.newaxis ]

        # If random sample from uniform distribution is less than the epsilon parameter then predict action, else take a random action
        if np.random.uniform() < self.epsilon:
            # Forward propagate to get q values of outputs
            actions_q_value = self.sess.run(self.q_eval_outputs, feed_dict={self.X: observation})

            # Get index of maximum q value
            action = np.argmax(actions_q_value)
        else:
            # Random action
            action = np.random.randint(0, self.n_y)

        return action

    def replace_target_net_parameters(self):
        print("target parameters replaced")
        t_params = tf.get_collection('target_net_params')
        e_params = tf.get_collection('eval_net_params')

        # Assign the parameters trained in the eval net to the target net
        self.sess.run( [ tf.assign(t,e) for t, e in zip(t_params, e_params) ] )

    def learn(self):
        # Replace target params
        if self.learn_step_counter % self.replace_target_iter == 0:
            self.replace_target_net_parameters()

        # Save checkpoint
        if self.learn_step_counter % (self.replace_target_iter * 10) == 0:
            if self.save_path is not None:
                save_path = self.saver.save(self.sess, self.save_path)
                print("Model saved in file: %s" % save_path)

        # Get a memory sample
        index_range = min(self.memory_counter, self.memory_size)
        sample_index = np.random.choice(index_range, size=self.batch_size)

        batch_memory_s = self.memory_s[ :,sample_index ]
        batch_memory_a = self.memory_a[ sample_index ]
        batch_memory_r = self.memory_r[ sample_index ]
        batch_memory_s_ = self.memory_s_[ :,sample_index ]

        # Forward propagate eval and target nets to get q values of actions
        q_next_outputs, q_eval_outputs = self.sess.run([self.q_next_outputs, self.q_eval_outputs], feed_dict={
            self.X_: batch_memory_s_,
            self.X: batch_memory_s
        })

        # Create copy of eval net outputs that we just forward propagated
        q_target_outputs = q_eval_outputs.copy()

        # Setup array of index for batch e.g. for batch size 32 it will be [0, 1, 2, ...31]
        batch_index = np.arange(self.batch_size, dtype=np.int32)

        # Get memory actions
        actions_index = batch_memory_a.astype(int)

        # Generate Q target values with Bellman equation
        q_target_outputs[ actions_index, batch_index ] = batch_memory_r + self.reward_decay * np.max(q_next_outputs, axis=0)

        # Train eval network
        _, self.cost = self.sess.run([self.train_op, self.loss], feed_dict={ self.X: batch_memory_s, self.Y: q_target_outputs } )

        # Save cost
        self.cost_history.append(self.cost)

        # Increase epsilon to make it more likely over time to get actions from predictions instead of from random sample
        self.epsilon = min(self.epsilon_max, self.epsilon + self.epsilon_greedy_increment)
        self.learn_step_counter += 1

    def build_eval_network(self, n_l1, n_l2, W_init, b_init):
        ###########
        # EVAL NET
        ###########
        self.X = tf.placeholder(tf.float32, [self.n_x, None], name='s')
        self.Y = tf.placeholder(tf.float32, [self.n_y, None ], name='Q_target')

        with tf.variable_scope('eval_net'):
            # Store variables in collection
            c_names = ['eval_net_params', tf.GraphKeys.GLOBAL_VARIABLES]

            with tf.variable_scope('parameters'):
                W1 = tf.get_variable('W1', [n_l1, self.n_x], initializer=W_init, collections=c_names)
                b1 = tf.get_variable('b1', [n_l1, 1], initializer=b_init, collections=c_names)
                W2 = tf.get_variable('W2', [n_l2, n_l1], initializer=W_init, collections=c_names)
                b2 = tf.get_variable('b2', [n_l2, 1], initializer=b_init, collections=c_names)
                W3 = tf.get_variable('W3', [self.n_y, n_l2], initializer=W_init, collections=c_names)
                b3 = tf.get_variable('b3', [self.n_y, 1], initializer=b_init, collections=c_names)

            # First layer
            with tf.variable_scope('layer_1'):
                Z1 = tf.matmul(W1, self.X) + b1
                A1 = tf.nn.relu( Z1 )
            # Second layer
            with tf.variable_scope('layer_2'):
                Z2 = tf.matmul(W2, A1) + b2
                A2 = tf.nn.relu( Z2 )
            # Output layer
            with tf.variable_scope('layer_3'):
                Z3 = tf.matmul(W3, A2) + b3
                self.q_eval_outputs = Z3

        with tf.variable_scope('loss'):
            self.loss = tf.reduce_mean(tf.squared_difference(self.Y, self.q_eval_outputs))
        with tf.variable_scope('train'):
            self.train_op = tf.train.AdamOptimizer(self.lr).minimize(self.loss)

    def build_target_network(self, n_l1, n_l2, W_init, b_init):
        ############
        # TARGET NET
        ############
        self.X_ = tf.placeholder(tf.float32, [self.n_x, None], name="s_")

        with tf.variable_scope('target_net'):
            c_names = ['target_net_params', tf.GraphKeys.GLOBAL_VARIABLES]

            with tf.variable_scope('parameters'):
                W1 = tf.get_variable('W1', [n_l1, self.n_x], initializer=W_init, collections=c_names)
                b1 = tf.get_variable('b1', [n_l1, 1], initializer=b_init, collections=c_names)
                W2 = tf.get_variable('W2', [n_l2, n_l1], initializer=W_init, collections=c_names)
                b2 = tf.get_variable('b2', [n_l2, 1], initializer=b_init, collections=c_names)
                W3 = tf.get_variable('W3', [self.n_y, n_l2], initializer=W_init, collections=c_names)
                b3 = tf.get_variable('b3', [self.n_y, 1], initializer=b_init, collections=c_names)

            # First layer
            with tf.variable_scope('layer_1'):
                Z1 = tf.matmul(W1, self.X_) + b1
                A1 = tf.nn.relu( Z1 )
            # Second layer
            with tf.variable_scope('layer_2'):
                Z2 = tf.matmul(W2, A1) + b2
                A2 = tf.nn.relu( Z2 )
            # Output layer
            with tf.variable_scope('layer_3'):
                Z3 = tf.matmul(W3, A2) + b3
                self.q_next_outputs = Z3

    def plot_cost(self):
        import matplotlib
        matplotlib.use("MacOSX")
        import matplotlib.pyplot as plt
        plt.plot(np.arange(len(self.cost_history)), self.cost_history)
        plt.ylabel('Cost')
        plt.xlabel('Training Steps')
        plt.show()
