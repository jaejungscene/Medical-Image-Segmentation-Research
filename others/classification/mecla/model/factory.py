import os
from pathlib import Path

import timm
import torch
import torch.nn as nn
import torchvision
from torch.nn.parallel import DistributedDataParallel


def get_model(args):
    if args.model_type == 'torchvision':
        model = torchvision.models.__dict__[args.model_name](
            num_classes=args.num_classes,
            pretrained=args.pretrained
        ).cuda(args.device)
    elif args.model_type == 'timm':
        model = timm.create_model(
            args.model_name,
            in_chans=args.in_channels,
            num_classes=args.num_classes,
            # drop_path_rate=args.drop_path_rate,
            pretrained=args.pretrained
        ).cuda(args.device)
    else:
        raise Exception(f"{args.model_type} is not supported yet")

    if args.checkpoint_path and Path(args.checkpoint_path).exists():
        args.log(f"load model weight from {args.checkpoint_path}")
        state_dict = torch.load(args.checkpoint_path, map_location='cpu')
        for key in ['model', 'state_dict']:
            if key in state_dict:
                state_dict = state_dict[key]
        for fc_name in ['fc', 'head', 'classifier', 'adv_classifier']:
            fc_weight = f"{fc_name}.weight"
            fc_bias = f"{fc_name}.bias"
            if fc_weight in state_dict and model.num_classes != state_dict[fc_weight].shape[0]:
                args.log('popping out head')
                state_dict.pop(fc_weight)
                state_dict.pop(fc_bias)
        model.load_state_dict(state_dict, strict=False)

    return model

def get_ddp_model(model, args):
    if args.channels_last:
        model = model.to(memory_format=torch.channels_last)

    if args.sync_bn:
        model = nn.SyncBatchNorm.convert_sync_batchnorm(model)

    if args.distributed:
        ddp_model = DistributedDataParallel(model, device_ids=[args.gpu])
    else:
        ddp_model = None

    return model, ddp_model