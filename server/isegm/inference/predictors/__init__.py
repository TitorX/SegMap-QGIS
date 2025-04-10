import torch
from isegm.inference.transforms import ZoomIn
from .base import BasePredictor
from .sam import SAMPredictor


def get_predictor(net, brs_mode, device,
                  prob_thresh=0.49,
                  with_flip=True,
                  zoom_in_params=dict(),
                  predictor_params=None,
                  compile=False):
    predictor_params_ = {
        'optimize_after_n_clicks': 1
    }

    if zoom_in_params is not None:
        zoom_in = ZoomIn(**zoom_in_params)
    else:
        zoom_in = None

    try:
        if compile:
            net = torch.compile(net)
    except Exception as e:
        print(f"Warning: Failed to compile the model. Error: {e}")
        compile = False

    if isinstance(net, (list, tuple)):
        assert brs_mode == 'NoBRS', "Multi-stage models support only NoBRS mode."

    if brs_mode == 'NoBRS':
        if predictor_params is not None:
            predictor_params_.update(predictor_params)
        predictor = BasePredictor(net, device, zoom_in=zoom_in, with_flip=with_flip, **predictor_params_)
    elif brs_mode == 'SAM':
        if predictor_params is not None:
            predictor_params_.update(predictor_params)
        predictor = SAMPredictor(net, device, zoom_in=zoom_in, with_flip=with_flip, **predictor_params_) 
    else:
        raise NotImplementedError

    return predictor
