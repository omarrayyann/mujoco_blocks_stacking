import mujoco
import mujoco.viewer
import numpy as np
import time
from Utils.utils import *
from controller import OpsaceController
from mujoco_ar import MujocoARConnector
import random
import threading
from collections import deque

class ImitationSimulation:
    
    def __init__(self):

        # Configs
        self.scene_path = 'Environment/scene.xml'
        self.mjmodel = mujoco.MjModel.from_xml_path(self.scene_path)
        self.mjdata = mujoco.MjData(self.mjmodel)
        self.dt = 0.002
        self.grasp = 0
        self.button = 0
        self.placement_time = -1
        self.rgb_renderer = mujoco.Renderer(self.mjmodel, height=120, width=160)
        self.depth_renderer = mujoco.Renderer(self.mjmodel, height=120, width=160)
        self.rgb_renderer = mujoco.Renderer(self.mjmodel, height=480, width=640)
        self.depth_renderer = mujoco.Renderer(self.mjmodel, height=480, width=640)
        self.depth_renderer.enable_depth_rendering()
        self.cameras = ["front_camera","side_camera","top_camera"]

        # Override the simulation timestep
        self.mjmodel.opt.timestep = self.dt
        self.frequency = 1000
        self.target_pos = np.array([0.5, 0.0, 0.4])
        self.target_rot = rotation_matrix_x(np.pi)@np.identity(3)
        self.pos_origin = self.target_pos.copy()
        self.rot_origin = self.target_rot.copy()
        self.target_quat = np.zeros(4)
        self.eef_site_name = 'eef'
        self.site_id = self.mjmodel.site(self.eef_site_name).id
        self.camera_name = 'gripper_camera'
        self.last_recording_time = -1
        self.camera_data = None
        self.joint_names = [
            "joint1",
            "joint2",
            "joint3",
            "joint4",
            "joint5",
            "joint6",
            "joint7",
            
        ]

        # Recording and Policy Related
        self.record = True
        self.run_policy = False
        self.recording_frequency = 10

        # Controller
        self.controller = OpsaceController(self.mjmodel,self.joint_names,self.eef_site_name)
        self.q0 = np.array([0, 0.2686, 0, -1.5423, 0, 1.3307, 0])
        self.dof_ids = np.array([self.mjmodel.joint(name).id for name in self.joint_names])
        self.actuator_ids = np.array([self.mjmodel.actuator(name).id for name in self.joint_names])
        self.grasp_actuator_id = self.mjmodel.actuator("fingers_actuator").id 
        self.mjdata.qpos[self.actuator_ids] = self.q0

        # MujocoAR Initialization
        self.mujocoAR = MujocoARConnector(mujoco_model=self.mjmodel,mujoco_data=self.mjdata)

        # Linking the target site with the AR position
        self.mujocoAR.link_site(
            name="eef_target",
            scale=3.0,
            position_origin=self.pos_origin,
            rotation_origin=self.rot_origin,
            toggle_fn=lambda: setattr(self, 'grasp', not self.grasp),
            # disable_rot=True,
        )

    def get_camera_data(self) -> dict:
        data = {}    
        for camera in self.cameras:
            self.rgb_renderer.update_scene(self.mjdata, camera)
            self.depth_renderer.update_scene(self.mjdata, camera)
            data[camera+"_rgb"] = self.rgb_renderer.render()
            data[camera+"_depth"] = self.depth_renderer.render()
        return data

    def start(self):
        
        threading.Thread(target=self.mac_launch).start()
        if self.run_policy:
            self.run_model()

    def mac_launch(self):

        if not self.run_policy:
            self.mujocoAR.start()


        set_site_pose(self.mjmodel,"eef_target",self.target_pos,self.target_rot)

        with mujoco.viewer.launch_passive(self.mjmodel,self.mjdata,show_left_ui=False,show_right_ui=False) as viewer:
            
            
            while viewer.is_running():

                step_start = time.time()

                tau = self.controller.get_tau(self.mjmodel,self.mjdata,self.target_pos,self.target_rot)
                self.mjdata.ctrl[self.actuator_ids] = tau[self.actuator_ids]
                self.mjdata.ctrl[self.grasp_actuator_id] = (self.grasp)*255.0
                mujoco.mj_step(self.mjmodel, self.mjdata)
                viewer.sync()

                
                self.target_pos = self.mjdata.site("eef_target").xpos.copy()
                self.target_rot = self.mjdata.site("eef_target").xmat.copy()

                time_until_next_step = self.dt - (time.time() - step_start)
                if time_until_next_step > 0:
                    time.sleep(time_until_next_step)

    

if __name__ == "__main__":

    sim = ImitationSimulation()
    sim.start()
