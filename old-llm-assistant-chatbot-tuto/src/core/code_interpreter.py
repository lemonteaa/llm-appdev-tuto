import outlines
from llama_cpp import LlamaGrammar

from infra.llm_provider import llm

from infra.docker_container_session import *

q = "Please generate a plot of the price of SP500 in the last week with hourly data, and save it to a file named sp500-plot.png."

react_grammar = """
thought-format ::= ( "Thought " iter ": " thought "\n" )
thought ::= [^\n]+
action-format ::= ( "Action " iter ": " action-type-branch "--")
action-type-branch ::= ( write-file-action | command-action | exit-action )

command-action ::= ( "Terminal command\n" "> " terminal-command "\n")
terminal-command ::= [^\n]+

exit-action ::= "Exit\n"

write-file-action ::= ( "Write files\n" (write-individual-file)+ "Finish.\n" )
write-individual-file ::= ( "File name: `" file-name-pattern "`\n" "File content:\n```\n" file-content "```\n" )
file-name-pattern ::= ("./" [^`]+)
file-content ::= [^`]*

root ::= (thought-format action-format)
"""

@outlines.prompt
def code_interpreter_prompt(request, homedir, history):
    """
BEGIN_INSTRUCTION
This is code interpreter. You, as an AI assistant, can design and execute python program on behalf of the user to accomplish various goals.
Setup:
- The python program will be executed in a sandboxed enviornment with python3.10 and pip3 already installed.
- Terminal access is also given, sudo apt-get is allowed. OS is ubuntu 20.
- Public internet access is allowed.
- Access to the user's home folder at `{{ homedir }}` (including creating subfolders etc) is allowed.
- In your program, anything printed to stdout will be shown to you, but no stdin access is given directly.
- Terminal output will also be printed to you.
- Access to the sandbox/code interpreter is interactive - you can perform one action at each step, and use the result/feedback to iterate and refine until you achieve your goal.

Instruction:
You should engage in a thought loop, explaining what you would do based on the current state of the code interpreter/results of previous actions. You will also pay attention to any technical details.
In that loop, you should repeat thought-action-observation:
- Thought is your internal monologue to decide on what to do next based on all available informations.
- Action is where you execute an action. Three types of actions are possible with their own format requirements:
  - "Write files" is where you will create new files by entering the text.
  - "Terminal command" is where you will execute a terminal command.
  - "Exit" is when you are done and want to leave code interpreter. (See below)
- Observation is where the system will return the result of your terminal command.

When you're accomplished your goal, choose the action type: "Exit".
You will then be exfiltrated by the system into another section where you are free to write the final answer, with access to your whole transcript.

Example format for reference:

Thought 1: I should install system dependencies.
Action 1: Terminal command
> sudo apt-get update && sudo apt install htop -y
--
Observation 1:
<transcript of terminal output>

Thought 2: I should now create the python program.
Action 2: Write files
File name: `./main.py`
File content:
```
import json
print("Hello")
```
File name: `./requirements.txt`
File content:
```
json
```
Finish.
--
Observation 2: Success.

Thought 3: Let's run the python program.
Action 3: Terminal command
> pip install -r requirements.txt && python main.py
--
Observation 3:
<transcript of terminal output>
...
Hello

Thought 4: We've successfully printed "Hello" to our screen.
Action 4: Exit
--

(Above is just a sample, feel free to be more elaborate in your internal monologue.)
END_INSTRUCTION

User query:
{{ request }}

Assistant:
{% for h in history %}
{{ h }}
{% endfor %}
    """




def code_interpreter_loop(request, session_name):
    conf = DockerContainerConfig()
    try:
        codeInterpreter = DockerCodeInterpreterSession("../code-int-storages")
        history = []
        done = False
        codeInterpreter.start_session(session_name, conf)
        while not done:
            prompt = code_interpreter_prompt(request, conf.bind_dir, history)
            response = llm(prompt=prompt, stop=["--"], grammar=LlamaGrammar.from_string(react_grammar))
            parsed_response = parse_response(response["choices"][0]["text"])
            if parsed_response["action_type"] == "Exit":
                done = True
                print("Code interpreter DONE!")
            elif parsed_response["action_type"] == "Terminal Command":
                commandOutput = codeInterpreter.run_single_command(parsed_response["command"], work_dir=conf.bind_dir)
                parsed_response["observation"] = commandOutput
            elif parsed_response["action_type"] == "Write files":
                pass # TODO
            else:
                raise ValueError()
            history.append(parsed_response)
    except BaseException as e:
        print(e)
    finally:
        codeInterpreter.stop_session()
