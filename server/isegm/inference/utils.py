from pathlib import Path
import torch
from isegm.utils.serialization import load_model


def load_is_model(checkpoint, device, eval_ritm, **kwargs):
    if isinstance(checkpoint, (str, Path)):
        state_dict = torch.load(checkpoint, map_location='cpu')
        # print("Load pre-trained checkpoint from: %s" % checkpoint)
    else:
        state_dict = checkpoint

    if isinstance(state_dict, list):
        model = load_single_is_model(state_dict[0], device, eval_ritm, **kwargs)
        models = [load_single_is_model(x, device, eval_ritm, **kwargs) for x in state_dict]

        return model, models
    else:
        return load_single_is_model(state_dict, device, eval_ritm, **kwargs)


def load_single_is_model(state_dict, device, eval_ritm, **kwargs):
    model = load_model(state_dict['config'], eval_ritm, **kwargs)
    model.load_state_dict(state_dict['state_dict'], strict=True)

    for param in model.parameters():
        param.requires_grad = False
    model.to(device)
    model.eval()

    return model
