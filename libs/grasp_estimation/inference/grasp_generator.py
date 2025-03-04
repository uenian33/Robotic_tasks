import os
import time

import matplotlib.pyplot as plt
import numpy as np
import torch

# from libs.camera.custom_camera import CustomCamera
# from libs.camera.camera_data import CameraData

from libs.grasp_estimation.hardware.device import get_device
from libs.grasp_estimation.inference.post_process import post_process_output
from libs.grasp_estimation.utils.dataset_processing.grasp import detect_grasps
from libs.grasp_estimation.utils.visualisation.plot import plot_grasp

# libs from motoman remote control https://github.com/norkator/nx100-remote-control/blob/b7a4392f0e182670986ca9488ccd58a3d09ae8b1/XboxController.py#L41
import nx100_remote_control
from nx100_remote_control.module import Commands, Utils, Gripper

import cv2


class GraspGenerator:
    def __init__(self, camera, cam_data, saved_model_path, cam_id, visualize=False):
        self.saved_model_path = saved_model_path
        self.camera = camera  # CustomCamera()

        self.saved_model_path = saved_model_path
        self.model = None
        self.device = None

        self.cam_data = cam_data  # CameraData(include_depth=True, include_rgb=True)

        # Init robot
        nx100_remote_control.MOCK_RESPONSE = False

        # Connect to camera
        # self.camera.connect()

        # Load camera pose and depth scale (from running calibration)
        # self.cam_pose = np.loadtxt('saved_data/camera_pose.txt', delimiter=' ')
        # self.cam_depth_scale = np.loadtxt('saved_data/camera_depth_scale.txt', delimiter=' ')
        # self. =

        homedir = os.path.join(os.path.expanduser('~'), "grasp-comms")
        self.grasp_request = os.path.join(homedir, "grasp_request.npy")
        self.grasp_available = os.path.join(homedir, "grasp_available.npy")
        self.grasp_pose = os.path.join(homedir, "grasp_pose.npy")

        if visualize:
            self.fig = plt.figure(figsize=(10, 10))
        else:
            self.fig = None

        self.SPEED = 30
        self.WAIT_FOR = 0.25  # seconds
        self.COORDINATE_SYSTEM = 0

    def load_model(self):
        print('Loading model... ')
        self.model = torch.load(self.saved_model_path)
        # Get the compute device
        self.device = get_device(force_cpu=False)

    def generate(self, visualize=False):
        # Get RGB-D image from camera
        image_bundle = self.camera.get_image_bundle()
        rgb = image_bundle[0]  # ['rgb']
        rgb = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB)
        depth = image_bundle[1]  # ['aligned_depth']
        # depth = cv2.cvtColor(depth,cv2.COLOR_GRAY2BGR)
        # print(rgb.shape, depth.shape)
        x, depth_img, rgb_img = self.cam_data.get_data(rgb=rgb, depth=depth)

        # Predict the grasp pose using the saved model
        with torch.no_grad():
            xc = x.to(self.device)
            pred = self.model.predict(xc)
            #print(pred)

        q_img, ang_img, width_img = post_process_output(pred['pos'], pred['cos'], pred['sin'], pred['width'])
        grasps = detect_grasps(q_img, ang_img, width_img)

        if visualize:
            plot_grasp(fig=self.fig, rgb_img=self.cam_data.get_rgb(rgb, False), grasps=grasps, save=False)
        # print(grasps)

        # """
        # Get grasp position from model output

        # the image resize scale
        curr_im_h, curr_im_w = depth.shape[0], depth.shape[1]
        origin_h, origin_w = 960, 1280
        xy_scale = origin_w / curr_im_w

        # the xyz offset between camera and gripper
        z_offset = 1 * 110.7  # original 130.7
        x_offset = -55.87
        y_offset = 50.77

        #print(depth[grasps[0].center[0], grasps[0].center[1]])
        pos_z = self.camera.depth_scale * depth[grasps[0].center[0], grasps[0].center[
            1]] - 0.04  # self.camera.left_intrinsics[0][0] / depth[grasps[0].center[0], grasps[0].center[1]] - 0.04
        pos_x = np.multiply(grasps[0].center[1] * xy_scale - self.camera.left_intrinsics[0][2],
                            pos_z / self.camera.left_intrinsics[0][0])
        pos_y = np.multiply(grasps[0].center[0] * xy_scale - self.camera.left_intrinsics[1][2],
                            pos_z / self.camera.left_intrinsics[1][1])

        if pos_z == 0:
            return

        target = np.asarray([pos_x, pos_y, pos_z])
        target.shape = (3, 1)
        print('target: ', target, grasps[0].angle, pos_z)
        c_pose = self.get_end_effector_position()


        angle = grasps[0].angle / np.pi * 180

        target_robot_pose = [c_pose.x + pos_x * 10 + x_offset,
                             c_pose.y - pos_y * 10 + y_offset,
                             c_pose.z - pos_z * 10 + z_offset,
                             c_pose.tx,
                             c_pose.ty,
                             c_pose.tz + angle]


        return target_robot_pose  # np.append(target_position, target_angle)

    def run(self):
        # Gripper.write_gripper_open()
        # while True:
        grasp_pose = self.generate()
        """
        Commands.write_linear_move(MoveL.MoveL(
                0, int(self.SPEED), self.COORDINATE_SYSTEM,
                grasp_pose[0],
                grasp_pose[1],
                grasp_pose[2], 
                grasp_pose[3],
                grasp_pose[4],
                grasp_pose[5], 
                Utils.binary_to_decimal(0x00000001)
            ))

        # should check when reaching but here just wait
        time.sleep(5)


        Gripper.write_gripper_close()
        """

        """
        while True:
            if np.load(self.grasp_request):
                self.generate()
                np.save(self.grasp_request, 0)
                np.save(self.grasp_available, 1)
            else:
                time.sleep(0.1)
        """

    def get_end_effector_position(self):
        return Commands.read_current_specified_coordinate_system_position('0', '0')
