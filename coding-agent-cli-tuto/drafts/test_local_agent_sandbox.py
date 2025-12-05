from rich.console import Console
from rich.syntax import Syntax

from rich import print as richprint
from rich.panel import Panel

#syntax = Syntax(my_code, "python", theme="monokai", line_numbers=True)

from datetime import datetime

from art import text2art

console = Console()

# Print welcome banner
console.print(text2art("Mini Code", font="tarty1"), style="cyan3")

"""
Tool registry
"""

from collections import OrderedDict
import traceback

class ToolRegistry:
    def __init__(self):
        self.tools = OrderedDict()
    
    def register_tool(self, name, desc, schema, fn, metadata={}):
        self.tools[name] = { "name": name, "desc": desc, "schema": schema.model_json_schema(), "fn": fn, "metadata": metadata }
    
    def get_tool_list(self):
        tool_list = []
        for k_name, v_detail in self.tools.items():
            openai_tool_spec = {
                'type': 'function',
                'function': {
                    'name': k_name,
                    'description': v_detail["desc"],
                    'parameters':  v_detail["schema"],
                    'strict': True
                }
            }
            tool_list.append(openai_tool_spec)
        return tool_list
    
    def call_tool_dynamic_single_sync_raw(self, name, tool_args):
        try:
            fn = self.tools[name]["fn"]
            result = fn(**tool_args)
            return result
        except Exception as e:
            traceback.print_exc()
            diagnostic = f'{e.__class__.__module__}.{e.__class__.__name__}: {e} {repr(e)}'
            print(diagnostic)
            return f"Encountered Error for this instance of tool use: {diagnostic}"
    
    def get_metadata(self, name):
        return self.tools[name]["metadata"]


central_tool_registry = ToolRegistry()

#central_tool_registry.register_tool(name='web_search', desc=web_search_tool_desc, schema=WebSearchParam, fn=web_search)


"""
Coding sandbox infra
"""

# From https://github.com/lemonteaa/llm-chatbot-tuto/blob/main/src/infra/docker_container_session.py

from pathlib import Path
import docker

from dataclasses import dataclass

import os
import io

loop_command = "/bin/bash -c -- 'while true; do sleep 30; done;'"

@dataclass(frozen=True)
class DockerContainerConfig:
    image: str | docker.models.images.Image = "python:3.12"
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

class DockerImageBuilder:
    def __init__(self):
        self.client = docker.from_env()
        self.image_obj = None
        self.image_id = None
    
    def build(self, dockerfile_str : str):
        image, build_log = self.client.images.build(fileobj= io.BytesIO( str.encode(dockerfile_str)) )
        self.image_obj = image
        self.image_id = image.id
        # DONE: handle log
        self.build_log = build_log
    
    def print_log(self, console):
        for log_item in self.build_log:
            if "stream" in log_item:
                console.log(log_item["stream"])


my_tech_stack_image = """FROM nikolaik/python-nodejs:latest

ARG git_user_name=AI-Agent
ARG git_user_email=agent@example.com

USER root

RUN apt update && apt-get install -y tree git tmux sudo
RUN echo "pn ALL=(root) NOPASSWD:ALL" > /etc/sudoers.d/pn && chmod 0440 /etc/sudoers.d/pn

RUN git config --global init.defaultBranch main
RUN git config --global user.name $git_user_name
RUN git config --global user.email $git_user_email

WORKDIR /tmp

RUN wget -O cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
RUN mv cloudflared /usr/local/bin && chmod a+x /usr/local/bin/cloudflared

RUN wget https://github.com/caddyserver/caddy/releases/download/v2.10.2/caddy_2.10.2_linux_amd64.tar.gz
RUN tar -xvzf caddy_2.10.2_linux_amd64.tar.gz
RUN mv caddy /usr/local/bin/caddy && chmod a+x /usr/local/bin/caddy

USER pn
WORKDIR /home/pn
"""

USER_HOME_DIR = "/home/pn"
# = "/teamspace/studios/this_studio"


cont_builder = DockerImageBuilder()

with console.status("[bold orange]Building container image...", spinner='dots2') as status:
    cont_builder.build(dockerfile_str = my_tech_stack_image)
cont_builder.print_log(console=console)
console.log(f"Image saved: {cont_builder.image_id}")

AGENT_LOCAL_HOME = "myagent"
now = datetime.now()
formatted_date_time = now.strftime("%Y%m%d_%H%M%S")

sandbox = DockerCodeInterpreterSession(storage_dir=os.path.join( os.getcwd(), AGENT_LOCAL_HOME))
with console.status("[bold orange]Starting container...", spinner='dots2') as status:
    sandbox.start_session(session_name= str(formatted_date_time), container_config=DockerContainerConfig(image=cont_builder.image_obj , bind_dir=USER_HOME_DIR) )

LOCAL_USER_HOME_DIR = os.path.join( os.getcwd(), AGENT_LOCAL_HOME, formatted_date_time)
console.log(f"Container started. Local folder: {LOCAL_USER_HOME_DIR}")




"""
tools:
1. read_single_file_enriched
2. write_files_unified_diff
3. write_single_file_vanilla_fallback
4. execute_command_simple
5. execute_command_interactively
6. list_command_shell_sessions
7. poll_interactive_command_shell_output
8. signal_agent_completed
9. report_live_preview_url
"""


"""
Define the tool fns and register
"""

import tarfile
import io
import tempfile

import pygments
from pygments.lexers import guess_lexer

def rich_print_source_code(console, content, lang=None):
    # Autodetect language
    if lang is None:
        try:
            lexer = guess_lexer(content)
            console.log(lexer.aliases)
            lang = lexer.aliases[0]
        except pygments.util.ClassNotFound:
            console.log("not found")
            lang = "text"
    console.log(lang)
    syntax = Syntax(content, lang, theme="ansi_light", background_color="white", line_numbers=True)
    console.print(syntax)

def read_single_file_enriched(filepath, uniform_format=True):
    with open(os.path.join(USER_HOME_DIR, filepath), 'r') as file:
        lines = file.readlines()

    if uniform_format:
        max_line_number = len(lines)
        line_number_format = f"{{:0{len(str(max_line_number))}}}"
    else:
        line_number_format = "{}"

    enriched_content = []
    original_content = []
    for i, line in enumerate(lines, start=1):
        line_number = line_number_format.format(i)
        enriched_content.append(f"{line_number} |{line}")
        original_content.append(line)
    
    # Frontend hook
    rich_print_source_code(console=console, content="".join(original_content))

    header_str = f"Content of {filepath}:\n"
    return header_str + "".join(enriched_content)


def write_files_unified_diff_after_editmode(repo_root, file_content):
    # Frontend hook
    rich_print_source_code(console=console, content=file_content)
    # Main
    obj_stream = io.BytesIO()
    tmp_file_name = None
    with tarfile.open(fileobj=obj_stream, mode='w|') as tmp_tar, tempfile.NamedTemporaryFile(mode="wb+") as tmp_file:
        tmp_file.write(file_content.encode("utf-8"))
        tmp_file.flush()
        tmp_file.seek(0) # http://stackoverflow.com/questions/49074623/ddg#49074745
        obj_info = tmp_tar.gettarinfo(fileobj=tmp_file)
        tmp_file_name = obj_info.name
        console.log(obj_info, tmp_file_name)
        tmp_tar.addfile(obj_info, tmp_file)
    sandbox.container.put_archive('/', obj_stream.getvalue())
    return True
    #return sandbox.run_single_command(command=f"git apply /tmp/{tmp_file_name}", work_dir=os.path.join(USER_HOME_DIR, repo_root)) #DONE: relative path? for repo_root

def write_single_file_vanilla_fallback_after_editmode(filepath, file_content):
    # Frontend hook
    rich_print_source_code(console=console, content=file_content)
    with open(os.path.join(LOCAL_USER_HOME_DIR, filepath), mode="w+", encoding="utf-8") as f:
        f.write(file_content)
    return f"File written to {filepath}"



def execute_command_simple(command, cwd = USER_HOME_DIR):
    return sandbox.run_single_command(command=command, work_dir=cwd)


interactive_shells = {}
current_max_tmux_id = 0

TMUX_SESSION = "vibe-code"
TMUX_SOCKET_DIR = "/tmp/agent-tmux-sockets"
TMUX_SOCKET = f"{TMUX_SOCKET_DIR}/agent.sock"

DEFAULT_SLEEP_SECONDS = 3

#tmux -S "$SOCKET" new -d -s "$SESSION" -n shell

console.log("Initializing tmux in container...")
sandbox.run_single_command(command=f"mkdir -p {TMUX_SOCKET_DIR}", work_dir=USER_HOME_DIR)
sandbox.run_single_command(command=f"tmux -S {TMUX_SOCKET} new -d -s {TMUX_SESSION} -n shell", work_dir=USER_HOME_DIR)
console.log("Okay!")



def execute_command_interactively(command_key_sequence, shell_name, wait_seconds = DEFAULT_SLEEP_SECONDS):
    global current_max_tmux_id
    if shell_name in interactive_shells:
        # Lookup id then send to tmux window
        tmux_id = interactive_shells.get(shell_name)
    else:
        # Create new tmux window, then remember the shell_name - id mapping
        sandbox.run_single_command(command=f"tmux -S {TMUX_SOCKET} new-window", work_dir=USER_HOME_DIR)
        current_max_tmux_id += 1
        interactive_shells[shell_name] = current_max_tmux_id
        tmux_id = current_max_tmux_id
    # Then send the key sequence in tmux eitherway
    sandbox.run_single_command(command=f"tmux -S {TMUX_SOCKET} send-keys -t {TMUX_SESSION}:{tmux_id}.0 -- {command_key_sequence}", work_dir=USER_HOME_DIR)
    time.sleep(wait_seconds)
    return sandbox.run_single_command(command=f"tmux -S {TMUX_SOCKET} capture-pane -p -J -t {TMUX_SESSION}:{tmux_id}.0 -S -200", work_dir=USER_HOME_DIR)

def list_command_shell_sessions():
    return list(interactive_shells.keys())

def poll_interactive_command_shell_output(shell_name, wait_seconds = DEFAULT_SLEEP_SECONDS):
    if shell_name not in interactive_shells:
        raise ValueError(f"The shell named: {shell_name}, does not exists.")
    tmux_id = interactive_shells.get(shell_name)
    time.sleep(wait_seconds)
    return sandbox.run_single_command(command=f"tmux -S {TMUX_SOCKET} capture-pane -p -J -t {TMUX_SESSION}:{tmux_id}.0 -S -200", work_dir=USER_HOME_DIR)

#from datetime import datetime
#now = datetime.now()
#formatted_date_time = now.strftime("%Y-%m-%d %H:%M:%S")
#print(formatted_date_time)

def signal_agent_completed(repos, additional_files):
    for repo in repos:
        sandbox.run_single_command(command=f"git archive --format=zip --output {USER_HOME_DIR}/export_{repo}.zip main", work_dir=os.path.join(USER_HOME_DIR, repo))
    sandbox.run_single_command(command="tar -czvf export_others.tar.gz " + " ".join(additional_files), work_dir=USER_HOME_DIR)
    return "project exported."

def report_live_preview_url(url):
    richprint(Panel(f"[link={url}]{url}[/link]", title="Live Preview Available"))
    return "sent preview URL to UI."



import time
#time.sleep(3)
#sandbox.stop_session()

#res1 = read_single_file_enriched("old.py")
#res2 = read_single_file_enriched("vanilla.txt")

#print(res1)
#print(res2)

#with open("hi.c", "r") as f:
#    src = f.read()

myurl = "https://huggingface.co/"
richprint(Panel(f"[link={myurl}]{myurl}[/link]", title="Live Preview Available"))


try:
    #write_files_unified_diff_after_editmode(repo_root=None, file_content=src)

    while True:
        cmd = console.input(prompt="Enter command:")
        #res = execute_command_simple(command=cmd)
        res = execute_command_interactively(command_key_sequence=cmd, shell_name="testing")
        console.log(list_command_shell_sessions())
        console.log(res)
finally:
    sandbox.stop_session()
