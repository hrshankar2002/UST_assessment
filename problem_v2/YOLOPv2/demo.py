#!/usr/bin/env python3
import argparse
import time
from pathlib import Path
import cv2
import torch

from utils.utils import (
    time_synchronized, select_device, increment_path,
    scale_coords, xyxy2xywh, non_max_suppression, split_for_trace_model,
    driving_area_mask, lane_line_mask, plot_one_box, show_seg_result,
    AverageMeter, LoadImages
)


def make_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', nargs='+', type=str, default='data/weights/yolopv2.pt', help='model.pt path(s)')
    parser.add_argument('--source', type=str, default='data/input.MP4', help='file/dir, 0 for webcam')
    parser.add_argument('--img-size', type=int, default=640, help='inference size (px)')
    parser.add_argument('--conf-thres', type=float, default=0.3, help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.45, help='NMS IoU threshold')
    parser.add_argument('--device', default='0', help='cuda device(s), e.g. 0 or 0,1 or cpu')
    parser.add_argument('--save-conf', action='store_true', help='save confidences in --save-txt labels')
    parser.add_argument('--save-txt', action='store_true', help='save detection results to .txt')
    parser.add_argument('--nosave', action='store_true', help='do not save images/videos')
    parser.add_argument('--classes', nargs='+', type=int, help='filter by class: --class 0 or --class 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--project', default='export', help='save results to project/name')
    parser.add_argument('--name', default='run', help='save results to project/name')
    parser.add_argument('--exist-ok', action='store_true', help='existing project/name ok')
    return parser


def detect(opt):
    # Directories
    save_img = not opt.nosave and not opt.source.endswith('.txt')
    save_dir = Path(increment_path(Path(opt.project) / opt.name, exist_ok=opt.exist_ok))
    label_dir = save_dir / 'labels'
    label_dir.mkdir(parents=True, exist_ok=True)
    lane_dir = save_dir / 'lane'
    drive_dir = save_dir / 'drivable'
    lane_dir.mkdir(parents=True, exist_ok=True)
    drive_dir.mkdir(parents=True, exist_ok=True)

    # Metrics
    inf_time = AverageMeter()
    waste_time = AverageMeter()
    nms_time = AverageMeter()

    # Load model
    device = select_device(opt.device)
    model = torch.jit.load(opt.weights[0], map_location=device)
    half = device.type != 'cpu'
    if half:
        model.half()
    model.to(device).eval()

    # Dataloader
    stride = 32
    dataset = LoadImages(opt.source, img_size=opt.img_size, stride=stride)

    # Warmup
    if device.type != 'cpu':
        model(torch.zeros(1, 3, opt.img_size, opt.img_size).to(device).type_as(next(model.parameters())))

    t0 = time.time()
    for path, img, im0s, vid_cap in dataset:
        img = torch.from_numpy(img).to(device)
        img = img.half() if half else img.float()
        img /= 255.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        # Inference
        t1 = time_synchronized()
        [pred, anchor_grid], seg, ll = model(img)
        t2 = time_synchronized()

        # Trace workaround
        tw1 = time_synchronized()
        pred = split_for_trace_model(pred, anchor_grid)
        tw2 = time_synchronized()

        # NMS
        t3 = time_synchronized()
        pred = non_max_suppression(
            pred, opt.conf_thres, opt.iou_thres,
            classes=opt.classes, agnostic=opt.agnostic_nms
        )
        t4 = time_synchronized()

        # Segmentation masks
        da_seg_mask = driving_area_mask(seg)  # H×W bool
        ll_seg_mask = lane_line_mask(ll)     # H×W bool

        # Save masks
        frame = getattr(dataset, 'frame', 0)
        fn = f"frame{frame:05d}.png"
        cv2.imwrite(str(lane_dir / fn), (ll_seg_mask * 255).astype('uint8'))
        cv2.imwrite(str(drive_dir / fn), (da_seg_mask * 255).astype('uint8'))

        # Process detections
        for i, det in enumerate(pred):
            p = Path(path)
            gn = torch.tensor(im0s.shape)[[1, 0, 1, 0]]
            if det is not None and len(det):
                det[:, :4] = scale_coords(img.shape[2:], det[:, :4], im0s.shape).round()

                # Write .txt
                if opt.save_txt:
                    txt_path = label_dir / (p.stem + f'_{frame}')
                    for *xyxy, conf, cls in det.cpu().numpy().tolist():
                        xywh = (xyxy2xywh(torch.tensor(xyxy).view(1, 4)) / gn).view(-1).tolist()
                        line = ([cls, *xywh, conf] if opt.save_conf else [cls, *xywh])
                        with open(txt_path.with_suffix('.txt'), 'a') as f:
                            f.write(('%g ' * len(line)).rstrip() % tuple(line) + '\n')

                # Draw boxes
                if save_img:
                    for *xyxy, conf, cls in det.cpu().numpy().tolist():
                        plot_one_box(xyxy, im0s, line_thickness=2)

        # Display & save visuals
        print(f'Done. ({t2 - t1:.3f}s)')
        show_seg_result(im0s, (da_seg_mask, ll_seg_mask), is_demo=True)

        if save_img:
            save_path = str(save_dir / p.name)
            if dataset.mode == 'image':
                cv2.imwrite(save_path, im0s)
            else:
                # video writer logic (omitted for brevity; same as original)
                pass

        # Update times
        inf_time.update(t2 - t1, img.size(0))
        nms_time.update(t4 - t3, img.size(0))
        waste_time.update(tw2 - tw1, img.size(0))

    print(f'inf: {inf_time.avg:.4f}s/img, nms: {nms_time.avg:.4f}s/img, total: {time.time() - t0:.3f}s')


if __name__ == '__main__':
    opt = make_parser().parse_args()
    print(opt)
    with torch.no_grad():
        detect(opt)
