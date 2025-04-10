from time import time

import numpy as np
import torch

from isegm.inference import utils
from isegm.inference.clicker import Clicker

try:
    get_ipython()
    from tqdm import tqdm_notebook as tqdm
except NameError:
    from tqdm import tqdm


def evaluate_dataset(dataset, predictor, **kwargs):
    all_ious = []
    all_classes = []
    all_sizes = []

    start_time = time()
    for index in tqdm(range(len(dataset)), leave=False):
        sample = dataset.get_sample(index)

        if not hasattr(sample, 'classes_list'):
            # dummy classes_list
            sample.classes_list = sample.objects_ids

        for object_id, object_class in zip(sample.objects_ids, sample.classes_list):
            sample_gt_mask = sample.gt_mask(object_id)
            _, sample_ious, _ = evaluate_sample(sample.image,
                                                sample_gt_mask,
                                                predictor,
                                                sample_id=index,
                                                **kwargs)
            all_ious.append(sample_ious)
            all_classes.append(object_class)
            all_sizes.append((sample_gt_mask > 0).sum())

    end_time = time()
    elapsed_time = end_time - start_time

    return all_ious, elapsed_time, \
        {'ious': all_ious, 'classes': all_classes, 'sizes': all_sizes}


def evaluate_sample(image, gt_mask, predictor, max_iou_thr,
                    pred_thr=0.49, min_clicks=1, max_clicks=20,
                    sample_id=None, callback=None):
    clicker = Clicker(gt_mask=gt_mask)
    pred_mask = np.zeros_like(gt_mask)
    ious_list = []

    with torch.no_grad():
        predictor.set_input_image(image)

        for click_indx in range(max_clicks):
            clicker.make_next_click(pred_mask)
            pred_probs = predictor.get_prediction(clicker)
            pred_mask = pred_probs > pred_thr

            iou = utils.get_iou(gt_mask, pred_mask)
            ious_list.append(iou)

            # import matplotlib.pyplot as plt
            # c = np.array([i.coords for i in clicker.clicks_list])
            # p = np.array(['green' if i.is_positive else 'red' for i in clicker.clicks_list])
            # fig, axes = plt.subplots(2, 2)
            # axes = axes.flatten()
            # axes[0].imshow(image)
            # axes[1].imshow(gt_mask)
            # axes[1].scatter(c[:, 1], c[:, 0], c=p)
            # axes[2].imshow(pred_mask)
            # axes[2].scatter(c[:, 1], c[:, 0], c=p)
            # axes[3].imshow(gt_mask != pred_mask)
            # axes[3].scatter(c[:, 1], c[:, 0], c=p)
            # plt.show()

            if iou >= max_iou_thr and click_indx + 1 >= min_clicks:
                if callback is not None:
                    callback(image, gt_mask, pred_probs, iou,
                            sample_id, click_indx, clicker.clicks_list, True,
                            predictor.zoom_in)
                break

            if callback is not None:
                callback(image, gt_mask, pred_probs, iou,
                         sample_id, click_indx,
                         clicker.clicks_list, False,
                         predictor.zoom_in)

        return clicker.clicks_list, np.array(ious_list, dtype=np.float32), pred_probs
