import logging

logger = logging.getLogger("experiment")

import logging

import torch
import copy

from torch import nn
from torch.nn import functional as F
import oml
logger = logging.getLogger("experiment")


class Learner(nn.Module):
    """
    """

    def __init__(self, learner_configuration, backbone_configuration=None):
        """

        :param learner_configuration: network config file, type:list of (string, list)
        :param imgc: 1 or 3
        :param imgsz:  28 or 84
        """
        super(Learner, self).__init__()

        self.config = learner_configuration
        self.backbone_config = backbone_configuration

        self.vars = nn.ParameterList()

        self.vars = self.parse_config(self.config, nn.ParameterList())
        self.context_backbone = None

    def parse_config(self, config, vars_list):

        

        for i, info_dict in enumerate(config):
   
            if info_dict["name"] == 'conv2d':
                w, b = oml.nn.conv2d(info_dict["config"], info_dict["adaptation"], info_dict["meta"])
                vars_list.append(w)
                vars_list.append(b)

           
            elif info_dict["name"] == 'conv1d':
                w, b = oml.nn.conv1d(info_dict["name"],info_dict["config"], info_dict["adaptation"], info_dict["meta"])
                vars_list.append(w)
                vars_list.append(b) 
   
    
                
            elif info_dict["name"] == 'LSTM':
                w, b = oml.nn.LSTM(info_dict["config"], info_dict["adaptation"], info_dict["meta"])
                vars_list.append(w)
                vars_list.append(b)  
 
            elif info_dict["name"] == 'linear':
                param_config = info_dict["config"]
                w, b = oml.nn.linear(info_dict["name"],param_config["out"], param_config["in"], info_dict["adaptation"], info_dict["meta"])
 
                vars_list.append(w)
                vars_list.append(b)


            elif info_dict["name"] in ['tanh', 'rep', 'relu', 'upsample', 'avg_pool2d', 'max_pool2d', 'maxPool1d', 'dropout',
                                       'flatten', 'reshape', 'leakyrelu', 'sigmoid', 'rotate']:
                continue
            else:
                #print(info_dict["name"])
                raise NotImplementedError
        return vars_list

    def add_rotation(self):
        self.rotate = nn.Parameter(torch.ones(2304,2304))
        torch.nn.init.uniform_(self.rotate)
        self.rotate_inverse = nn.Parameter(torch.inverse(self.rotate))
        # #print(self.rotate.shape)
        # #print(self.rotate_inverse.shape)
        # quit()
        logger.info("Inverse computed")


    def reset_vars(self):
        """
        Reset all adaptation parameters to random values. Bias terms are set to zero and other terms to default values of kaiming_normal_
        :return:
        """
        for var in self.vars:
            if var.adaptation is True:
                if len(var.shape) > 1:
                    torch.nn.init.kaiming_normal_(var)
                else:
                    torch.nn.init.zeros_(var)
         
    def reset_vars_meta_test(self):
        """
        Reset all adaptation parameters to random values. Bias terms are set to zero and other terms to default values of kaiming_normal_
        :return:
        """
        for var in self.vars:
            if 'linear' in var.id:
                if len(var.shape) > 1:
                    torch.nn.init.kaiming_normal_(var)
                else:
                    torch.nn.init.zeros_(var)
            
        
         
    def forward(self, x, vars=None, config=None, sparsity_log=False, rep=False):
        """
        """

        x = x.float()
        if vars is None:
            vars = self.vars

        #print('X ', x.shape)
        

        if config is None:
            config = self.config

        idx = 0

        for layer_counter, info_dict in enumerate(config):
            name = info_dict["name"]
            if name == 'conv2d':
                w, b = vars[idx], vars[idx + 1]
                x = F.conv2d(x, w, b, stride=info_dict['config']['stride'], padding=info_dict['config']['padding'])
                idx += 2
                
            elif name == 'conv1d':
                w, b = vars[idx], vars[idx + 1]
                #print('conv1d x shape', x.shape)
                x = F.conv1d(x, w, b, stride=info_dict['config']['stride'], padding=info_dict['config']['padding'])
                ##print("conv1d w shape ",  w.shape, "b shape ",  b.shape, "x shape ",  x.shape)
                idx += 2

            elif name == 'linear':            
                w, b = vars[idx], vars[idx + 1]
                #print('linear x shape', x.shape)
               # #print("linear w shape ",  w.shape, "b shape ",  b.shape, "x shape ",  x.shape)
                x = F.linear(x, w, b)
                idx += 2
                
            elif name == 'LSTM':            
                w, b = vars[idx], vars[idx + 1]
                #print('LSTM x shape', x.shape)
                #print('hidden size' , info_dict['config']['hidden'])
                #print('input size',info_dict['config']['filters'])
                x, _ = nn.LSTM(x, hidden_size=info_dict['config']['hidden']) #,w, b, input_size=info_dict['config']['filters'], hidden_size=info_dict['config']['hidden'])
                idx += 2
                
            elif name == 'flatten':
                x = x.view(x.size(0), -1)
                ##print("flatten x shape ",  x.shape)
                
            elif name == 'maxPool1d':
                    x = F.max_pool1d(x,info_dict['config']['kernal'], info_dict['config']['stride'])
                #    #print("maxPool1d x shape ",  x.shape)

            elif name == 'dropout':
                    x = F.dropout(x,info_dict['config']['p'])
                 #   #print("dropout x shape ",  x.shape)

            elif name == 'rotate':
                # pass
                x = F.linear(x, self.rotate)
                x = F.linear(x, self.rotate_inverse)
              #  #print("x shape ",  x.shape)

            elif name == 'reshape':
                continue

            elif name == 'rep':
                if rep:
                    return x

            elif name == 'relu':
                x = F.relu(x)
               # #print("x shape ",  x.shape)

            else:
                raise NotImplementedError
        assert idx == len(vars)
        return x

    def update_weights(self, vars):

        for old, new in zip(self.vars, vars):
            #old.data = new.data
            old.data = copy.deepcopy(new.data)


    def get_adaptation_parameters(self, vars=None):
        """
        :return: adaptation parameters i.e. parameters changed in the inner loop
        """
        if vars is None:
            vars = self.vars
            
        return list(filter(lambda x: x.adaptation, list(vars)))
    
    def get_adaptation_parameters_meta_test(self, vars=None):
        """
        :return: adaptation parameters i.e. parameters changed in the inner loop
        """
        if vars is None:
            vars = self.vars
            
        return [vars[-4], vars[-3], vars[-2],vars[-1]]
        
        return list(filter(lambda x: 'linear' in x.idx, list(vars)))    
    
    def get_forward_meta_parameters(self):
        """
        :return: adaptation parameters i.e. parameters changed in the inner loop
        """
        return list(filter(lambda x: x.meta, list(self.vars)))

    def parameters(self):
        """
        override this function since initial parameters will return with a generator.
        :return:
        """

        return self.vars
