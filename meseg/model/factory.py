import re
import timm
import numpy as np
import torch
import torch.nn as nn
import torchvision
from torch.nn.parallel import DistributedDataParallel
import monai.networks.nets as monai

from . import model_config
from . import transunet
from . import inception_transformer



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

    elif args.model_type == "monai":
        model = getattr(monai, args.model_name)(
            **getattr(model_config, args.model_name)()
        ).cuda(args.device)

    elif re.findall("transunet|inception", args.model_name):
        config = model_config.transunet()
        config.n_classes = args.num_classes
        modelconfig = args.model_name.split("_")
        if args.model_name.startswith("transunet"):
            config.block = "normal"
            model = transunet.TransUnet(config).cuda(args.device)
            if modelconfig[-1] == "pt":
                print("Load pretrained weights.....")
                weights = np.load(config.pretrained_path)
                model.load_from(weights)
                print("Successfully load pretrained weights!!")
        # {model_name}_d{hidden_size}_p{num_path}_f{pixshuf_factor}_{concat}
        else:
            config.block = "inception"
            config.hidden_size = int(modelconfig[2][1:]) # 768, 384, 192
            config.num_path = int(modelconfig[3][1:])
            config.pixshuf_factor = int(modelconfig[4][1:])
            config.concat = True if modelconfig[-2]=="concat" else False
            model = transunet.TransUnet(config).cuda(args.device)
            if modelconfig[-1] == "pt":
                print("Load pretrained weights.....")
                weights = torch.load(args.checkpoint_path)
                model.load_state_dict(weights)
                print("Successfully load pretrained weights!!")
    else:
        raise Exception(f"{args.model_type} is not supported yet")

    return model



def get_ddp_model(model, args):
    if args.channels_last:
        model = model.to(memory_format=torch.channels_last)

    if args.sync_bn:
        model = nn.SyncBatchNorm.convert_sync_batchnorm(model)

    if args.distributed:
        ddp_model = DistributedDataParallel(model, device_ids=[args.gpu])
    elif len(args.cuda) > 1:
        model = nn.DataParallel(model)
        ddp_model = None
    else:
        ddp_model = None

    return model, ddp_model