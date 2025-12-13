from rich.console import Console
from rich.syntax import Syntax

from rich import print as richprint
from rich.panel import Panel

from datetime import datetime

from art import text2art

console = Console(record=True)

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
    
    def run_single_command(self, command : str, work_dir = None, show_exit_code = True):
        if work_dir is None:
            my_work_dir = self.default_work_dir
        else:
            my_work_dir = work_dir
        result = self.container.exec_run(command, workdir=my_work_dir)
        if show_exit_code:
            return f"{result.output.decode("utf-8")}\n--\n[system] Exited with code {result.exit_code}."
        else:
            return f"{result.output.decode("utf-8")} "
    
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

RUN wget -O cloudflared -nv https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
RUN mv cloudflared /usr/local/bin && chmod a+x /usr/local/bin/cloudflared

RUN wget -nv https://github.com/caddyserver/caddy/releases/download/v2.10.2/caddy_2.10.2_linux_amd64.tar.gz
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
import time
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

import pathlib

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
    return sandbox.run_single_command(command=f"git apply /{tmp_file_name}", work_dir=os.path.join(USER_HOME_DIR, repo_root)) #DONE: relative path? for repo_root, also fix patch location bug

def write_single_file_vanilla_fallback_after_editmode(filepath, file_content):
    err_msg_abs = f"Validation error in file path {filepath}: This tool only supports edit within home directory, absolute path does not point to a location inside home dir or one of its subfolder."
    err_msg_rel_up = f"Validation error in file path {filepath}: This tool does not support parent dir relative path specification."
    # Frontend hook
    rich_print_source_code(console=console, content=file_content)
    # TODO: patchup dumbness of LLM model by intelligently detecting case
    #open_path = os.path.join(LOCAL_USER_HOME_DIR, filepath)
    p = pathlib.Path(filepath)
    if p.parts[0] == "/":
        if len(p.parts) < 4:
            return err_msg_abs
        if p.parts[1] != "home" or p.parts[2] != "pn":
            return err_msg_abs
        open_path = pathlib.Path(*p.parts[3:])
    elif p.parts[0] == "..":
        return err_msg_rel_up
    else:
        open_path = filepath
    with open(os.path.join(LOCAL_USER_HOME_DIR, open_path), mode="w+", encoding="utf-8") as f:
        f.write(file_content)
    return f"File written to {filepath}"



def execute_command_simple(command, wrap_in_bash, cwd = USER_HOME_DIR):
    if wrap_in_bash:
        final_cmd = f"bash -c '{command}'"
    else:
        final_cmd = command
    return sandbox.run_single_command(command=final_cmd, work_dir=cwd)


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
    return sandbox.run_single_command(command=f"tmux -S {TMUX_SOCKET} capture-pane -p -J -t {TMUX_SESSION}:{tmux_id}.0 -S -200", work_dir=USER_HOME_DIR, show_exit_code=False)

def list_command_shell_sessions():
    return list(interactive_shells.keys())

def poll_interactive_command_shell_output(shell_name, wait_seconds = DEFAULT_SLEEP_SECONDS):
    if shell_name not in interactive_shells:
        raise ValueError(f"The shell named: {shell_name}, does not exists.")
    tmux_id = interactive_shells.get(shell_name)
    time.sleep(wait_seconds)
    return sandbox.run_single_command(command=f"tmux -S {TMUX_SOCKET} capture-pane -p -J -t {TMUX_SESSION}:{tmux_id}.0 -S -200", work_dir=USER_HOME_DIR, show_exit_code=False)

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

"""
Subsection: Tool spec
"""

from pydantic import BaseModel, Field
import json

"""
#Example:
class WebSearchParam(BaseModel):
     model_config = dict(extra='forbid')
     language : str = Field(default="en", description="Prioritize results to pages in the specified language first.")

web_search_tool_desc = 'Perform *one* web search using a metasearch engine.'
"""


tool_descs = {
    "read_single_file_enriched": "Read the content of a single file in the container. Will return with line number annotation to make it easier for you to write patch.",
    "write_files_unified_diff": "Write to one or more file at once that are all inside a single git repo. Accept git unified diff format.",
    "write_single_file_vanilla_fallback": "Write to a single file. Will overwrite existing content if exists. Use as a fallback from `write_files_unified_diff`, or when creating new file.",
    "execute_command_simple": "Execute a terminal command and see the stdout/stderr. Underlying mechanism is similar to `docker exec`. Limitation: it is a direct execution in a non-shell enivornment. If you need shell, persistence, or interactivity, please use `execute_command_interactively` instead.",
    "execute_command_interactively": "In a persistent shell window, execute command interactively. Shell windows are identified by name, and new shells are created on demand if a non-existent shell name is specified. Actually, this is a slight misnomer as you can send control key sequence as well. Please be advised however that it uses tmux underneath for implementation, and due to some quirks, the command/key sequence you send may break if complex/deeply nested quoting is involved. Will return a capture of the shell after sending the commands and waiting for the specified time.",
    "list_command_shell_sessions": "List all the existing shell windows that are previously created by executing command interactively. Return list of the shell names.",
    "poll_interactive_command_shell_output": "Get the screen output of a shell window in text format using polling. Will wait for a time specified by you first to avoid thrashing/thundering herd problem.",
    "signal_agent_completed": "Indicate to the underlying system that you have completed the whole task.",
    "report_live_preview_url": "Report the live preview URL of the app you're working on. The underlying system will record it and present the URL to the user behind the scene through suitable UI, so that user may preview the app.",
}

class ReadSingleFileParam(BaseModel):
    model_config = dict(extra='forbid')
    filepath : str = Field(description="Path to the file to read. Relative to user home directory. Example: rust_template/src/main.rs (Will get translated to /home/pn/rust_template/src/main.rs by system behind the scene)")

class WriteUnifiedDiffParam(BaseModel):
    model_config = dict(extra='forbid')
    repo_root : str = Field(description="git repo to apply the diff patch onto, specified through the git repo root directory, relative to user home directory. Example: if there is a git repo at /home/pn/rust_template, then please input rust_template for this field.")
    file_content: str = Field(description="Content of the file.")

class WriteSingleFileParam(BaseModel):
    model_config = dict(extra='forbid')
    filepath : str = Field(description="Path to the file to write. Relative to user home directory. Example: rust_template/src/main.rs (Will get translated to /home/pn/rust_template/src/main.rs by system behind the scene)")
    file_content: str = Field(description="Content of the file.")

class ExecuteCommandSimpleParam(BaseModel):
    model_config = dict(extra='forbid')
    command : str = Field(description="Command to execute.")
    cwd : str = Field(default=USER_HOME_DIR, description="Current Working Directory.")
    wrap_in_bash : bool = Field(description="If true, will wrap the command into `bash -c '<command>'` (Note the single quote is injected by the tool already). This will allow use of shell features. Downside is need more care about quote escape.")

class ExecuteCommandInteractiveParam(BaseModel):
    model_config = dict(extra='forbid')
    command_key_sequence : str = Field(description="Commands and/or key sequences to send. Behind the scene, it is appended to the command `tmux ... send-keys ... -- <your commands>`.\n\nExample 1: \"python -m http.server\" Enter\nExample 2: C-c\n\nThe first example illustrate how you'd do the interactive version of executing a single command, notice the quoting and needs to follow up with the enter key; while the second shows the syntax for control key sequence (C-c means Control-C).")
    shell_name : str = Field(description="Uniquely identifying name for the shell. Slug like and alphanumeric only, eg smoke-test01")
    wait_seconds : int = Field(default=DEFAULT_SLEEP_SECONDS, description="How many seconds to wait after sending the key sequence before recording the terminal output once.")

class ListCommandShellsParam(BaseModel):
    model_config = dict(extra='forbid')

class PollCommandShellParam(BaseModel):
    model_config = dict(extra='forbid')
    shell_name : str = Field(description="Name of the shell to poll from.")
    wait_seconds : int = Field(default=DEFAULT_SLEEP_SECONDS, description="How many seconds to wait before recording the terminal output once.")

class SignalCompleteParam(BaseModel):
    model_config = dict(extra='forbid')
    repos : list[str] = Field(description="List of git repos to export to the user, specified as path (of the git repo root directory) relative from home directory.")
    additional_files : list[str] = Field(description="Additional files outside of git repo to also export to the user, specified as file path relative from home directory.")

class ReportLivePreviewParam(BaseModel):
    model_config = dict(extra='forbid')
    url : str = Field(description="The preview URL. Example format: https://huggingface.co/")


central_tool_registry.register_tool(name="read_single_file_enriched", desc=tool_descs["read_single_file_enriched"], schema=ReadSingleFileParam, fn=read_single_file_enriched)

central_tool_registry.register_tool(name="execute_command_simple", desc=tool_descs["execute_command_simple"], schema=ExecuteCommandSimpleParam, fn=execute_command_simple)
central_tool_registry.register_tool(name="execute_command_interactively", desc=tool_descs["execute_command_interactively"], schema=ExecuteCommandInteractiveParam, fn=execute_command_interactively)
central_tool_registry.register_tool(name="list_command_shell_sessions", desc=tool_descs["list_command_shell_sessions"], schema=ListCommandShellsParam, fn=list_command_shell_sessions)
central_tool_registry.register_tool(name="poll_interactive_command_shell_output", desc=tool_descs["poll_interactive_command_shell_output"], schema=PollCommandShellParam, fn=poll_interactive_command_shell_output)
central_tool_registry.register_tool(name="signal_agent_completed", desc=tool_descs["signal_agent_completed"], schema=SignalCompleteParam, fn=signal_agent_completed)
central_tool_registry.register_tool(name="report_live_preview_url", desc=tool_descs["report_live_preview_url"], schema=ReportLivePreviewParam, fn=report_live_preview_url)

unified_diff_editmode_metadata = {
    "param_name": "file_content",
    "param_desc": "Content of the diff file in git unified diff format, UTF-8 encoding. The content you write below will be saved as a temporary file and then applied immediately, therefore the diff/patch file itself does not need any name specified. You should output just the content itself **without** surrounding it with markdown blockquote, nor any other commentary."
}
write_singlefile_editmode_metadata = {
    "param_name": "file_content",
    "param_desc": "Text content of the file in UTF-8 encoding. You should output just the content itself **without** surrounding it with markdown blockquote, nor any other commentary. (However, outputing markdown blockquote as part of the file content itself, if you are currently writing a .md file say, is fair game. This is the distinction between the object level (the .md file) and the meta level)"
}

central_tool_registry.register_tool(name="write_files_unified_diff", desc=tool_descs["write_files_unified_diff"], schema=WriteUnifiedDiffParam, fn=write_files_unified_diff_after_editmode, metadata={ "editmode": unified_diff_editmode_metadata })
central_tool_registry.register_tool(name="write_single_file_vanilla_fallback", desc=tool_descs["write_single_file_vanilla_fallback"], schema=WriteSingleFileParam, fn=write_single_file_vanilla_fallback_after_editmode, metadata={ "editmode": write_singlefile_editmode_metadata })


"""
Prompts
"""

#"Other assumption: B2C, Fullstack webdev"


task_overview_prompt = """
You are a fully autonomous coding agent in single round mode. User will give you the request, which will be your overall goal. You will repeatedly reason and then act (by using the provided tools) to fulfill the user request. The tools are your interface to a semi-persistent coding sandbox inside of which you will work to produce the code artifacts. We assume the request is a greenfield coding project, and so the coding sandbox allocated to you at the beginning of each session will be a fresh one.
"""

env_tech_spec_prompt = """
## Tech spec of coding sandbox

- Docker container, OS is debian
- NodeJS and Python installed with modern toolings:

    Node.js: 22.x
    npm: 10.x
    yarn: stable
    pnpm: included
    Python: latest
    pip: latest
    pipenv: latest
    poetry: latest
    uv: latest

- cloudflared and caddy both installed in /usr/local/bin and so can be called directly
- git already configured with user name and email globally
- You work as the uid 1000 user: pn
- User have passwordless sudo access
- Volume mount at user's home directory (anything outside are ephemeral )

"""


recommended_workflow_prompt = """
## Recommended Workflow

1. Begin by analyzing the user request and plan ahead on your overall agent trajectory. You may also want to produce documents such as Requirement Analysis and System/Tech Design (things like API schema, DB schema, UI flow design, UML doc such as sequence diagram...) etc (though see the behavioral guideline). Place these documents in a new folder under the home directory.
2. Perform project scaffolding. In this phase, you will initialize one or more repo, each of which is a separate git repo living in their own distinct folders under the home directory. Depending on the tech stack, use appropiate toolings to scaffold it with the initial code files. This might either be tech stack specific commands, or alternatively, if it's the convention, to (semi-)manually write the code files.
3. You will then start up a live dev enviornment, by running appropiate commands for each system component. For (fullstack) web dev, you will do additional actions to expose the services on a URL that the user can visit to see the result. (Refer to the Official Tech Cheatsheet section for hints on the concrete commands and files to achive this)
4. Then, you begin the development/coding steps. Do so incrementally in a code - bugfix - git commit cycle.
5. When you have implemented all features, or exhausted your attempts, you wrap up by first writing documentations within each system component's repo (mainly their respective README file), and then producing a sign-off/devlog document that summarizes this coding session.
"""

behavioral_guideline_prompt = """
## General Behavioral guideline

- Because this is single round, you will be unable to ask clarifying question on user requirment. Try to make reasonable guess if necessary (but don't try too hard - it's okay to say I don't know and leave the truly ambigous part out)
- Pursue your goal with moderate intensity. In general, it is okay to give up if you have been struggling on a particular point and have already made multiple (diverse) attempts but it seems there is no sign of progress/resolution. In that case, simply move on to other part - better to have a partially completed job than a stalled one. Just remember to indicate clearly in your final devlog about which part you have given up on.
- For the various design documentations (both at the initial design phase and during the final technical documentation phase), gauge how much you should write based on, and proportional to the actual scope/scale/complexity of the project.
- The git commits can be granular (but don't overdo it). This help with the iterative development style, and also because keeping the repo in a clean state often would allow the use of powerful command line tool for repo analysis.
- Because you operate autonomously, the expectation is that you will not be able to ask for user feedback or assistance. And because you don't have vision capability, certain type of testing will be out of scope and that's okay. That being said, consider the following type of tests that you can still do to check your work: 1) Smoke testing - such as reading the command line output of the live server or build/compile command to see if there's error message, 2) Unit testing, 3) Manual testing, such as running a curl command to directly check backend behavior. Due to budget constrain, it might not be prudent to always do all the tests all the time - instead, be strategic about it. The key point is to use testing and iterative development as a mindset to help yourself - for example, not doing any test, and then making multiple big changes is bad because if the code then breaks, it would be hard to triage the bug. 


"""

tool_calling_guideline_prompt = """
## Tool calling guideline

### General

You can call multiple tools in a single response. If you intend to call multiple tools and there are no dependencies between them, make all independent tool calls in parallel. Maximize use of parallel tool calls where possible to increase efficiency. However, if some tool calls depend on previous calls to inform dependent values, do NOT call these tools in parallel and instead call them sequentially. For instance, if one operation must complete before another starts, run these operations sequentially instead. Never use placeholders or guess missing parameters in tool calls.

### Specific

The set of tools have been carefully designed to balance various trade-offs - flexibility/power, convinience/ease of use, etc.

From a technical perspective, there are two types of tools:
1. Ordinary tool - call them as usual
2. Indicator tool - semi-dummy tool used as either agent lifecycle management, or for end user interaction.

On the other hand, from the coding agent domain perspective, the tools can be classified as follow:

1. File IO

We settled down on three tools: read_single_file_enriched, write_files_unified_diff, write_single_file_vanilla_fallback.

Note that file or directory listing tool is absent because we believe that running suitable command line commands is more flexible, considering the possible variations of what you may exactly want to do. On the other hand, we DO strongly advise using the specialized tool to read file content (use parallel tool call if you want to read multiple files at once), because it will display the file contents annotated with line number. This is especially important because AI has a known weaknesses in keeping track of line numbers, which is essential to using the diff format correctly. For writing file, the tool requires the use of git unified diff format. This has many benefits: you can modify multiple files in one go, and you can skip the parts of the file that remain unchanged. Especially for long file, eliminating this redundancy is crucial because AI may get lost with superflorous repetitions, and because you may drool out when the text simply gets too long. That being said, using the diff format can be tricky and even best faith effort may fail, so we provide an escape hatch as a last resort. You are also allowed to use it in some special cases where it make sense (eg when creating a new file for the first time).

2. Command execution

There is one simple, plus three for interactive case: execute_command_simple, execute_command_interactively, list_command_shell_sessions, poll_interactive_command_shell_output.

The interactive counterpart is more powerful but more complex, it does have many use cases: for long running/continously running process such as server, when interactive input is needed to operate the program started by the command, or when a persistent shell enviornment is necessary, such as python venv.

You may create and use multiple interactive shell. Shell creation is implicit/implied whenever you specify an unused shell name, while calling the tool with a previously used shell name means sending the inputs/key combos to that existing shell. To see the outputs from an interactive shell, use the polling tool. To avoid the usual over-polling problem, you should set a reasonable wait time parameter.

3. Indicator tools

signal_agent_completed: call it when you've completed the whole assigned task. Remember to specify the set of git repos produced, as well as any additional files that are outside of git repo but relevant and should be saved. User will be able to download the git repos and the additional files you specified, but other files will be lost.

report_live_preview_url: By calling this tool, user will be able to visit the preview URL (otherwise user wouldn't know what the assigned preview URL is).

### Other Notes

- File and folder path are always specified relative to the user's home directory for all tool call arguments. For example, hello/foo/bar.txt would be translated by our system behind the scene into the absolute path of /home/pn/hello/foo/bar.txt . So you SHOULD NOT use absolute path for these tool call arguments. Our system will also handle trailing slash etc automatically.
- The exception to this rule is the cwd/current directory argument for the execute_command_simple tool, where an absolute path is expected.

"""


official_tech_cheatsheet_prompt = """
## Official Tech Cheatsheet

### Exposing web services

The officially sanctioned way to expose web service to the user is via using cloudflare's free tier tunnel. Quickstart command (in an interactive shell): `cloudflared tunnel --url http://localhost:7428`. Read the command's output to get the URL assigned by cloudflare and report it to user. Note that free tier have limitations - generally, we will get allocated a subdomain of a cloudflare controlled domain name, and we don't get to choice the name of the subdomain either, but that's okay. More importantly further subdomain is not allowed, so especially for things like fullstack, we recommend a setup of: cloudflared tunnel -> caddy -> reverse proxy to multiple local web services. (This is indeed a more substantive limitation because some user may prefer the subdomain method to allocate backend/frontend - https://api.example.com/ and https://example.com/, over the path prefix method - https://example.com/api and https://example.com/ - for aesthetic or other reason)

To use caddy, produce a Caddyfile inside a new, empty folder, then run this command in an interactive shell inside that folder: `caddy run`. It will try to validate the Caddyfile and use it as the config. Caddy has the advantage that it supports live/hot reload of config. For example, it may say that it finds the Caddyfile formating to need repair, then you can run this in that folder (non-interactive is okay): `caddy fmt --overwrite`. Whenever the Caddyfile is changed, trigger the running caddy server to reload config by issuing this command (non-interactive, separately from the running caddy process): `caddy reload`.

For the most common case of fullstack web dev with a frontend and backend component, an example Caddyfile is as follows:
```
{
        auto_https off
}

:7428 {
        handle_path /api/* {
                reverse_proxy 127.0.0.1:8000
        }
        handle_path /* {
                reverse_proxy localhost:5173
        }
}
```

Explanation:
- The first block is a global config, that turns off the automatic https cert stuff etc (which is a selling point of caddy but inappropiate in our particular context).
- Then, we config it to listen on the port 7428, and split/routes request based on the request URL. URL that begins with the path prefix /api/ are sent to the backend, while the rest are sent to the frontend. Note that prefix-stripping - a feature necessary since the components themselves are agnostic of the networking setup, is already implied by the tag `handle_path`.
- The use of `localhost` instead of `127.0.0.1` is necessary for the frontend when using vite, since vite by default uses a stricter request filter.

### Tech stack specific hints

When using pnpm to scaffold new frontend project, it uses an interactive form by default, which is challenging for AI agent like you to navigate even when using interactive shell, due to use of arrow key + color scheme limitation etc. So we strongly recommend you use the non-interactive version. Below is a command that works: `pnpm create vite <project name> --template react-ts --no-interactive`. Specifying the template explicitly skip one step, but `--no-interactive` is still necessary to skip the interactive prompt asking for optional features. Remember to run `pnpm install` afterward.

Project templates available:
    vanilla
    vanilla-ts
    vue
    vue-ts
    react
    react-ts
    react-swc
    react-swc-ts
    preact
    preact-ts
    lit
    lit-ts
    svelte
    svelte-ts
    solid
    solid-ts
    qwik
    qwik-ts

You can use . for the project name to scaffold in the current directory.

Although not recommended, for reference, in case you're using npm, notice the need for the extra `--` to hand over the extra arguments properly:

```
# npm 7+, extra double-dash is needed:
npm create vite@latest my-vue-app -- --template vue
```

By default, vite is strict about allowing external connection to the live preview server. Need to edit the file vite.config.ts, and set server.allowedHosts = true (in the JSON format where dot means object attribute etc).

For python project using venv, interactive shell will be necessary for the duration of the whole session. Below is a quick cheatsheet if using uv without poetry:
```
uv venv
source .venv/bin/activate
uv pip install ...
```

### General tech hints

For initial git commit, remember to run `git add .gitignore` separately after `git add *` before committing. (Or maybe it's because it should be `git commit .` instead?)

Use of intermediate level+ command line mastery can allow you to list project files in a powerful way. Below are some recommended pattern (though you may use your own if you have better ideas):

To list all files in a git repo in a ascii-art visual way that also shows the directory structure, while also filtering out files based on .gitignore: `git ls-tree -r --name-only HEAD | tree --fromfile`. Limitation: work best on a clean repo without uncommited changes, doesn't work before the initial git commit, also doesn't show detailed metadata such as modified date, size, ownership/access etc. Advantage is that this simultaneously let you see the project directory structure at a glance, while also list even files that are nested in multiple level of folders in a single command. Moreover, filtering away gitignore is crucial for some repos, such as frontend, where a typical node_modules have numerous files and will completely flood the output with noise. Unfortunately, although the tree command itself supports the --git-ignore flag in more recent version, our sandbox currently uses an older version.

"""

other_notes_prompt = """
## Other notes

### Reasoning, chat turn, and tool call

There is a change in Qwen policy. While previously adding your thoughts before the tool use/function call is optional, now it is *mandatory*. These thoughts will be shown in UI to user, so please use natural language in markdown format. Also, tool use/function call is mandatory in each turn until you're done.

### Folder layout example

/home/pn
|- /docs - Contain various design docs (.md files)
|- /frontend - git repo of the frontend
|- /backend - git repo of the backend

### Additional feedback based on your previous performance

- When using the interactive shell tool, you MUST surround command with quotes, and MUST follow it up with the key sequence Enter, if you want to actually run it.
Example:
Incorrect: `cd folder && pip install openai`
Correct: `"cd folder && pip install openai" Enter`

This point is **very important** so it is worth repeating - **The interactive shell tool will NOT run anything if you don't explicitly request it to press the Enter key like the example above!**

- If you executed the interactive shell tool, but the screen seems to be not updating even if you poll again separately, chances are, you have not sent the Enter key.

- Be extra careful around when to use quote/escape, taking into account the various level of nesting/context.

- You also seem to have mixed up the notion of relative vs absolute path. Remember, other than cwd in the simple command tool, all the file_path arguments in the file write tools are relative to user home directory!

- Additional behavioral guideline: after you scaffolded a repo, immediately git commit the repo if the scaffolding tool did not already made the first git commit on your behalf already. Some critical tools will not work on these newly created repo before the first git commit is made!

"""


unused_1 = "- The simple command execution tool is docker exec and NOT a shell, therefore it doesn't support bash specific features. **Important:** If you still want it, please use the `bash -c -- ...` trick."

final_prompt = """
[system notice] You have now completed the task. As part of hand-off, you have one last chance to send a markdown formated message to the user that summarize and wrap up everything. The message you reply below will be shown verbatim to the user's UI.
"""

next_turn_prompt = """
[system notice] all tool call requests processed. Please proceed to your next turn.
"""

def construct_system_prompt():
    system_prompt_set = [task_overview_prompt,
        env_tech_spec_prompt,
        recommended_workflow_prompt,
        behavioral_guideline_prompt,
        tool_calling_guideline_prompt,
        official_tech_cheatsheet_prompt,
        other_notes_prompt
    ]
    return "".join(system_prompt_set)

def construct_edit_mode_prompt(f_id, fn, tool_meta):
    ctx_str_1 = f"[system notice] Editing edit mode. We are currently at tool call id {f_id}, calling the tool {fn.name}, with these args: {fn.arguments}."
    ctx_str_2 = f"You should now supply the data for the remaining arg {tool_meta["param_name"]}. The tool has provided the following description and explanation for this arg: {tool_meta["param_desc"]}."
    ctx_str_3 = "Extra notice: if you are doing parallel tool call, note that the system is in the middle of executing the queued requests one by one, and will pick up your data in this round, and then continue the sequential execution as usual. Please be patient and do not proceed to your next turn of agentic action until you are told that all tool calls are processed."
    return "\n".join([ctx_str_1, ctx_str_2, ctx_str_3])

"""
Misc. setup
"""
from pathlib import Path

CONFIG_DIR = os.path.join( os.path.expanduser("~"), ".minicode")
LLM_CONFIG_FILE = os.path.join( CONFIG_DIR, "llm_provider_config.json")
Path(CONFIG_DIR).mkdir(parents=True, exist_ok=True)


@dataclass
class LLMConfig:
    base_url : str
    api_key : str
    model_id : str
    extra_body : dict

# Eg 1: llama.cpp
# extra_body = { "parse_tool_calls": True }
# Eg 2: vercel/openrouter AI gateway
# extra_body = { 'providerOptions': { 'gateway': { 'order': ['vertex', 'anthropic'] }}} # 'only' to disable nonmatching.



def obtain_llm_config(console):
    if os.path.isfile(LLM_CONFIG_FILE):
        # Read existing conf
        with open(LLM_CONFIG_FILE, "r") as f:
            data = json.load(f)
        console.print("[bold blue]Welcome back, user!\n")
    else:
        # Onboard user
        data = {}
        console.print("[bold blue]Welcome, new user. Before we begin, let's configure the LLM's OpenAI API compatible endpoint.\n")
        data["base_url"] = console.input("Enter the base URL> ")
        data["api_key"] = console.input("Enter the API key> ", password=True)
        data["model_id"] = console.input("Enter the model id> ")
        data["extra_body"] = json.loads( console.input("Enter any provider specific extra option to send, must be valid JSON (eg OpenRouter gateway option to auto-rank provider):\n> ") )
        with open(LLM_CONFIG_FILE, "w") as f:
            json.dump(data, f)
    return LLMConfig(**data)    


llm_config = obtain_llm_config(console=console)

console.log("LLM Provider configured.")
console.log("Initializing OpenAI client...")

import openai
from openai import OpenAI

cli = OpenAI(base_url=llm_config.base_url, api_key=llm_config.api_key)

console.log(f"OpenAI client version {openai.__version__} initialized.")

from tenacity import retry, wait_exponential

@retry(wait=wait_exponential(multiplier=1, min=4, max=20),
    before_sleep=lambda x: console.log("retrying..."))
def smoke_test():
    res = cli.chat.completions.create(model=llm_config.model_id, messages=[{"role": "user", "content": "this is a test, just say hi to me."}], stream=False)
    console.log(res)


"""
Main Agent Loop
"""

from rich.markdown import Markdown
from rich.pretty import Pretty


def main_call_llm(message_list, tool_required=True):
    if tool_required:
        tool_choice = "required"
    else:
        tool_choice = "none"
    #tool_choice = "auto"
    with console.status("[bold green]LLM is thinking...", spinner='dots2') as status:
        res = cli.chat.completions.create(
            model=llm_config.model_id,
            messages=message_list,
            tools=central_tool_registry.get_tool_list(),
            parallel_tool_calls=True,
            tool_choice=tool_choice,
            extra_body=llm_config.extra_body,
            stream=False,
        )
    return res


conversation = [
    { "role": "system", "content": construct_system_prompt() }
]

TERMINATOR_TOOL_NAME = "signal_agent_completed"

def main_agent_loop():
    done = False
    while not done:
        # Call LLM
        res = main_call_llm(conversation, tool_required=False) # will be False if 2 round method
        conversation.append(res.choices[0].message.model_dump())
        # Frontend hook: print content
        console.print( Markdown( str(res.choices[0].message.content) ))
        # Second round to enforce tool calling if using split method
        #res = main_call_llm(conversation)
        if res.choices[0].finish_reason != 'tool_calls':
            # New fix
            res2 = main_call_llm(conversation, tool_required=True)
            conversation[-1]["tool_calls"] = [ x.model_dump() for x in res2.choices[0].message.tool_calls ]
        
        #conversation.append(res.choices[0].message) #Second round append
        # Parallel tool call
        for idx, tool_call in enumerate(res.choices[0].message.tool_calls):
            fn = tool_call.function
            f_args = json.loads(fn.arguments)
            f_id = tool_call.id
            # Frontend hook: print tool call
            console.print( Panel( Pretty(f_args), title=f"Tool call: {fn.name}") )
            # Backend: run the tool
            # First check if it is edit mode tool
            tool_meta = central_tool_registry.get_metadata(fn.name) #DONE
            #if "editmode" in tool_meta:
            #    # Enter edit mode and one more round trip to LLM
            #    conversation.append({ "role": "user", "content": construct_edit_mode_prompt(f_id, fn, tool_meta["editmode"]) }) #bugfix
            #    res_edit = main_call_llm(conversation, tool_required=False)
            #    additional_arg = res_edit.choices[0].message.content
            #    f_args[tool_meta["param_name"]] = additional_arg # also bug
            #    # Frontend hook: display
            #    rich_print_source_code(console=console, content=additional_arg) #TODO: hardcode as we know it must be file, but in future?
            if "editmode" in tool_meta:
                rich_print_source_code(console=console, content=f_args[tool_meta["editmode"]["param_name"]])
            # Then actual call
            with console.status(f"[bold blue]Calling tool {fn.name}...", spinner='dots2') as status:
                f_ret = central_tool_registry.call_tool_dynamic_single_sync_raw(fn.name, f_args)
            # Frontend hook: just print
            console.print( Panel( f_ret, title=f"Tool call result for {fn.name}"))
            # Backend: append reply to prepare next round
            conversation.append({ "role": "tool", "tool_call_id": f_id, "content": f_ret })
            # Check terminal state
            # TODO: what if LLM stumble and have tool call after the signal complete tool?
            if fn.name == TERMINATOR_TOOL_NAME:
                done = True
            time.sleep(1)
            #if not done:
            #    conversation.append({ "role": "user", "content": next_turn_prompt })
        #else:
        #    # TODO: should be impossible but what if provider doesn't fully comply with OpenAI spec
        #    raise ValueError("Opps")
    # One last round
    console.rule("[bold green]Task completed!")
    console.print("LLM will now generates a final hand-off message...")
    conversation.append({ "role": "user", "content": final_prompt })
    res_final = main_call_llm(conversation, tool_required=False)
    console.print( Markdown( str(res_final.choices[0].message.content) ))



try:
    user_prompt = console.input(prompt="Tell LLM what project do you want it to do today:\n")
    conversation.append({ "role": "user", "content": user_prompt })
    console.log("Health check LLM API...")
    smoke_test()
    main_agent_loop()
    console.save_html(path= os.path.join( CONFIG_DIR, f"session_log_{formatted_date_time}.html" ))
finally:
    console.log(conversation)
    with open(os.path.join( CONFIG_DIR, f"debug_dump_{formatted_date_time}.json"), "w", encoding="utf-8") as f:
        json.dump(conversation, f)
    sandbox.stop_session()
