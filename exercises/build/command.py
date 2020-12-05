import argparse

# from git import Repo # pip install gitpython
import os

import docker
import nbformat  # install before?
from nbconvert.exporters import PythonExporter
import yaml
from dt_shell import DTCommandAbs, dtslogger
from dt_shell.env_checks import check_docker_environment
from utils.docker_utils import build_if_not_exist, \
    default_env, remove_if_running, get_remote_client, \
    pull_if_not_exist
from utils.networking_utils import get_duckiebot_ip
from utils.cli_utils import start_command_in_subprocess

usage = """

## Basic usage
    This is a helper for the exercises. 
    You must run this command inside an exercise folder. 

    To know more on the `exercise` commands, use `dts duckiebot exercise -h`.

        $ dts exercise build 

"""



BRANCH="daffy"
ARCH="amd64"
AIDO_REGISTRY="registry-stage.duckietown.org"
ROS_TEMPLATE_IMAGE="duckietown/challenge-aido_lf-template-ros:" + BRANCH + "-" + ARCH



class InvalidUserInput(Exception):
    pass


from dt_shell import DTShell


class DTCommand(DTCommandAbs):
    @staticmethod
    def command(shell: DTShell, args):
        prog = "dts exercise build"
        parser = argparse.ArgumentParser(prog=prog, usage=usage)

        parser.add_argument(
            "--staging",
            "-t",
            dest="staging",
            action="store_true",
            default=False,
            help="Should we use the staging AIDO registry?",
        )

        parser.add_argument(
            "--debug",
            "-d",
            dest="debug",
            action="store_true",
            default=False,
            help="Will give you a terminal inside the container",
        )

        parser.add_argument(
            "--clean",
            "-c",
            dest="clean",
            action="store_true",
            default=False,
            help="Will clean the build",
        )

        parsed = parser.parse_args(args)

        working_dir = os.getcwd()
        if not os.path.exists(working_dir + "/config.yaml"):
            msg = "You must run this command inside the exercise directory"
            raise InvalidUserInput(msg)

        config = load_yaml(working_dir + "/config.yaml")

        exercise_ws_dir = working_dir + "/exercise_ws"
        package_dir = exercise_ws_dir +"/src/"+config["exercise"]["notebook_settings"]["package_name"]
        
        notebook = config["exercise"]["notebook_settings"]["notebook"]

        convertNotebook(working_dir+f"/notebooks/{notebook}", notebook, package_dir)

        client = check_docker_environment()

        if parsed.staging:
            ros_template_image = AIDO_REGISTRY + "/" + ROS_TEMPLATE_IMAGE
        else:
            ros_template_image = ROS_TEMPLATE_IMAGE

        if parsed.debug:
            cmd = "bash"
        elif parsed.clean:
            cmd = ["catkin", "clean", "--workspace", "exercise_ws"]
        else:
            cmd = ["catkin", "build", "--workspace", "exercise_ws"]

        container_name = "ros_template_catkin_build"
        remove_if_running(client, container_name)
        ros_template_volumes = {}
        ros_template_volumes[working_dir + "/exercise_ws"] = {"bind": "/code/exercise_ws", "mode": "rw"}

        ros_template_params = {
            "image": ros_template_image,
            "name": container_name,
            "volumes": ros_template_volumes,
            "command": cmd,
            "stdin_open": True,
            "tty": True,
            "detach": True,
            "remove": True,
            "stream": True,
        }

        pull_if_not_exist(client, ros_template_params["image"])
        ros_template_container = client.containers.run(**ros_template_params)
        attach_cmd = "docker attach %s" % container_name
        start_command_in_subprocess(attach_cmd)

        dtslogger.info("Build complete")

def convertNotebook(filepath, filename, export_path) -> bool:
    import nbformat  # install before?
    from traitlets.config import Config

    filepath = filepath+".ipynb"
    if not os.path.exists(filepath):
        return False

    if not os.path.isfile(filepath):
        dtslogger.error("No such file "+filepath+". Make sure the config.yaml is correct.")
        exit(0)

    nb = nbformat.read(filepath, as_version=4)

    # clean the notebook:
    c = Config()
    c.TagRemovePreprocessor.remove_cell_tags = ("skip",)

    exporter = PythonExporter(config=c)

    # source is a tuple of python source code
    # meta contains metadata
    source, _ = exporter.from_notebook_node(nb)


    try:
        with open(export_path+"/src/"+filename+".py", "w+") as fh:
            fh.writelines(source)
    except Exception:
        return False

    return True


def load_yaml(file_name):
    with open(file_name) as f:
        try:
            env = yaml.load(f, Loader=yaml.FullLoader)
        except Exception as e:
            dtslogger.warn("error reading simulation environment config: %s" % e)
        return env