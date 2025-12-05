from pathlib import Path
import docker

from dataclasses import dataclass

loop_command = "/bin/bash -c -- 'while true; do sleep 30; done;'"

@dataclass(frozen=True)
class DockerContainerConfig:
    image: str = "python:3.12"
    bind_dir: str = "/usr/src/app"

class DockerCodeInterpreterSession:
    def __init__(self, storage_dir : str):
        self.client = docker.from_env()
        self.base_dir = Path(storage_dir)
    
    def _prepare_drive(self, session_name : str):
        mount_dir = self.base_dir.joinpath(session_name)
        mount_dir.mkdir(parents=True, exist_ok=True)
        return mount_dir
    
    def upload_files(self, session_name : str, files):
        my_dir = self._prepare_drive(session_name)
        for file in files:
            with open(my_dir.joinpath(file["path"]), "w") as f:
                f.write(file["content"])
    
    def start_session(self, session_name : str, container_config : DockerContainerConfig):
        # First prepare the drive
        mount_dir = self._prepare_drive(session_name)
        # Then setup the vol mapping
        vol_map = {}
        vol_map[str(mount_dir.absolute())] = {
            "bind": container_config.bind_dir,
            "mode": "rw"
        }
        # Finally start it
        cont = self.client.containers.run(container_config.image,
            detach=True,
            name=session_name,
            volumes=vol_map,
            command=loop_command)
        self.container = cont
        self.session_name = session_name
        self.default_work_dir = container_config.bind_dir

    def run_single_command(self, command : str, work_dir = None):
        if work_dir is None:
            my_work_dir = self.default_work_dir
        else:
            my_work_dir = work_dir
        result = self.container.exec_run(command, workdir=my_work_dir)
        return result.output.decode("utf-8")

    def stop_session(self):
        self.container.stop()
