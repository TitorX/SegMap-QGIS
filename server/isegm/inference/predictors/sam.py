import numpy as np
import torch
from segment_anything import SamPredictor
from .base import BasePredictor


class SAMPredictor(BasePredictor):
    def __init__(self, *args, **kwargs):
        kwargs['max_size'] = None
        kwargs['with_flip'] = False
        super().__init__(*args, **kwargs)
        self.sam_predictor = SamPredictor(self.net)

    def set_input_image(self, image):
        self.sam_predictor.set_image(image)

        image_nd = self.to_tensor(image)
        for transform in self.transforms:
            transform.reset()
        self.original_image = image_nd.to(self.device)
        if len(self.original_image.shape) == 3:
            self.original_image = self.original_image.unsqueeze(0)
        self.prev_prediction = torch.zeros_like(self.original_image[:, :1, :, :])

        self.low_res_masks = None

    def _get_prediction(self, image_nd, clicks_lists, is_image_changed):
        points_nd = self.get_points_nd(clicks_lists)
        prev_mask = getattr(self, 'low_res_masks', None)
        mask, _, low_res_masks = self.sam_predictor.predict(**points_nd,
                                                            mask_input=prev_mask,
                                                            multimask_output=False,
                                                            return_logits=True)
        self.low_res_masks = low_res_masks
        mask = torch.from_numpy(mask).unsqueeze(1) + 0.5
        return mask

    def get_points_nd(self, clicks_lists):
        input_points = []
        input_labels = []

        for clicks_list in clicks_lists:
            clicks_list = clicks_list[:self.net_clicks_limit]

            for click in clicks_list:
                input_points.append(click.coords[::-1])
                input_labels.append(1 if click.is_positive else 0)

        input_points = np.array(input_points)
        input_labels = np.array(input_labels)

        return {'point_coords': input_points, "point_labels": input_labels}
