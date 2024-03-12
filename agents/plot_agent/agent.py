import os
import re
import traceback
from typing import List
# from base_agent import BaseAgent
from .prompt import ERROR_PROMPT, INITIAL_SYSTEM_PROMPT, INITIAL_USER_PROMPT, VIS_SYSTEM_PROMPT, VIS_USER_PROMPT, ZERO_SHOT_COT_PROMPT
from agents.openai_chatComplete import completion_with_backoff
from agents.utils import fill_in_placeholders, get_error_message, is_run_code_success, run_code
from agents.utils import print_filesys_struture
from agents.utils import change_directory


class PlotAgent():
    """
    This class is responsible for plan generation. It is a subclass of BaseAgent.

    Attributes:
        abilities: A set indicating the abilities required by this agent.
    """

    def __init__(self, config, query, data_information=None):
        self.chat_history = []
        self.workspace = config['workspace']
        self.query = query
        self.data_information = data_information

    def generate(self, user_prompt, model_type, query_type, file_name):
        # TODO SYSTEM_PROMPT和USER_PROMPT的调整，目前的很粗糙
        # !去掉root node，因为一直找不到路径
        workspace_structure = print_filesys_struture(self.workspace)
        # workspace_structure = workspace_structure[workspace_structure.find('\n'):]
        information = {
            'workspace_structure': workspace_structure,
            'file_name': file_name,
            'query': user_prompt
        }

        if query_type == 'initial':
            messages = []
            messages.append({"role": "system", "content": fill_in_placeholders(INITIAL_SYSTEM_PROMPT, information)})
            messages.append({"role": "user", "content": fill_in_placeholders(INITIAL_USER_PROMPT, information)})
            print(messages)
        else:
            messages = []
            messages.append({"role": "system", "content": fill_in_placeholders(VIS_SYSTEM_PROMPT, information)})
            messages.append({"role": "user", "content": fill_in_placeholders(VIS_USER_PROMPT, information)})
            print(messages)

        self.chat_history = self.chat_history + messages
        return completion_with_backoff(messages, model_type)

    def get_code(self, response):
        # 匹配所有在```python和```之间的代码块
        all_python_code_blocks_pattern = re.compile(r'```python\s*([\s\S]+?)\s*```', re.MULTILINE)

        # 提取所有代码块并连接在一起
        all_code_blocks = all_python_code_blocks_pattern.findall(response)
        all_code_blocks_combined = '\n'.join(all_code_blocks)
        return all_code_blocks_combined
    def get_code2(self, response,file_name):
        '''这个函数是为了代码的最后尝试
        '''
        # 匹配所有在```和```之间的代码块
        all_python_code_blocks_pattern = re.compile(r'```\s*([\s\S]+?)\s*```', re.MULTILINE)

        # 提取所有代码块并连接在一起
        all_code_blocks = all_python_code_blocks_pattern.findall(response)
        all_code_blocks_combined = '\n'.join(all_code_blocks)
        if all_code_blocks_combined == '':
            #找到最后一个文件名那一列

            #直接找第一个import
            #我要的就是这两者之间的列
            response_lines = response.split('\n')
            code_lines = []
            code_start = False
            for line in response_lines:
                if line.find('import') == 0 or code_start:
                    code_lines.append(line)
                    code_start = True
                if code_start and line.find(file_name)!=-1 and line.find('(') !=-1 and line.find(')')!=-1 and line.find('(') < line.find(file_name)< line.find(')'): #要有文件名，同时要有函数调用

                    return '\n'.join(code_lines)
        return all_code_blocks_combined


    def run(self, query, model_type, query_type, file_name):
        try_count = 0
        image_file = file_name
        result = self.generate(query, model_type=model_type, query_type=query_type, file_name=file_name)
        while try_count < 4:
            # print(result)
            # self.chat_history.append({"role": "assistant", "content": result})
            if not isinstance(result, str):  # 如果返回的不是字符串，那么就是出错了
                return 'TOO LONG FOR MODEL', code
            if model_type != 'gpt-4':
                code = self.get_code(result)
                if code.strip() == '':
                    code = self.get_code2(result,image_file) #第二次尝试获得代码
                    if code.strip() == '':
                        code = result  #只能用原始回答
                        if code.strip() == '' and try_count == 0: #有可能是因为没有extend query写好了代码，所以他不写代码
                            code = self.get_code(query)
            else:
                code = self.get_code(result)
            self.chat_history.append({"role": "assistant", "content": result if result.strip() != '' else ''})
            # write code to workspace and run
            # print(code)

            file_name = f'code_action_{model_type}_{query_type}_{try_count}.py'
            with open(os.path.join(self.workspace, file_name), 'w') as f:
                f.write(code)
            error = None
            log = run_code(self.workspace, file_name)

            if is_run_code_success(log):
                if print_filesys_struture(self.workspace).find('.png') == -1:
                    log = log + '\n' + 'No plot generated.'
                    
                    self.chat_history.append({"role": "user", "content": fill_in_placeholders(ERROR_PROMPT,
                                                                                          {'error_message': f'No plot generated. When you complete a plot, remember to save it to a png file. The file name should be """{image_file}""".',
                                                                                           'data_information': self.data_information})})
                    try_count += 1
                    result = completion_with_backoff(self.chat_history, model_type=model_type)
                    # result = ""

                else:
                    return log, code

            else:
                error = get_error_message(log) if error is None else error
                # TODO error prompt
                self.chat_history.append({"role": "user", "content": fill_in_placeholders(ERROR_PROMPT,
                                                                                          {'error_message': error,
                                                                                           'data_information': self.data_information})})
                try_count += 1
                result = completion_with_backoff(self.chat_history, model_type=model_type)
                print(result)

        return log, ''

    def run_initial(self, model_type, file_name):
        print('========Plot AGENT Expert RUN========')
        self.chat_history = []
        log, code = self.run(self.query, model_type, 'initial', file_name)
        return log, code

    def run_vis(self, model_type, file_name):
        print('========Plot AGENT Novice RUN========')
        self.chat_history = []
        log, code = self.run(self.query, model_type, 'vis_refined', file_name)
        return log, code

    def run_one_time(self, model_type, file_name,query_type='novice',no_sysprompt=False):
        '''只进行一次尝试，并且不会进行任何的refine，没有system prompt'''
        print('========Plot AGENT Novice RUN========')
        message = []
        workspace_structure = print_filesys_struture(self.workspace)
        # workspace_structure = workspace_structure[workspace_structure.find('\n'):]
        information = {
            'workspace_structure': workspace_structure,
            'file_name': file_name,
            'query': self.query
        }
        if no_sysprompt:
            message.append({"role": "system", "content": ''''''})
        message.append({"role": "user", "content": fill_in_placeholders(INITIAL_USER_PROMPT, information)})
        result = completion_with_backoff(message, model_type)
        if model_type != 'gpt-4':
            code = self.get_code(result)
            if code == '':
                code = self.get_code2(result,file_name)
                if code == '':
                    code = result
        else:
            code = self.get_code(result)
        # write code to workspace and run
        # print(code)

        file_name = f'code_action_{model_type}_{query_type}_0.py'
        with open(os.path.join(self.workspace, file_name), 'w') as f:
            f.write(code)
        log = run_code(self.workspace, file_name)
        return log, code
    def run_one_time_zero_shot_COT(self, model_type, file_name,query_type='novice',no_sysprompt=False):
        '''只进行一次尝试，并且不会进行任何的refine，没有system prompt'''
        print('========Plot AGENT Novice RUN========')
        message = []
        workspace_structure = print_filesys_struture(self.workspace)
        # workspace_structure = workspace_structure[workspace_structure.find('\n'):]
        information = {
            'workspace_structure': workspace_structure,
            'file_name': file_name,
            'query': self.query
        }
        message.append({"role": "system", "content": ''''''})
        message.append({"role": "user", "content": fill_in_placeholders(ZERO_SHOT_COT_PROMPT, information)})
        result = completion_with_backoff(message, model_type)
        if model_type != 'gpt-4':
            code = self.get_code(result)
            if code == '':
                code = self.get_code2(result,file_name)
                if code == '':
                    code = result
        else:
            code = self.get_code(result)
        # write code to workspace and run
        # print(code)

        file_name = f'code_action_{model_type}_{query_type}_0.py'
        with open(os.path.join(self.workspace, file_name), 'w') as f:
            f.write(code)
        log = run_code(self.workspace, file_name)
        return log, code
# if __name__ == "__main__":
#     agent = ActionAgent('./workspace','print("hello world")')
#     print(agent.run())