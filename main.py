import paramiko
import socket
import threading
import openai
from os import environ

# Установите ваш API ключ OpenAI здесь
openai.api_key = environ['OPENAI_API_KEY']

# SSH server key
HOST_KEY = paramiko.RSAKey(filename='ssh_host_rsa_key')

# Инициализация истории команд
command_history = []

def handle_command_with_gpt(command):
    command_history.append(f"User: {command}")
    try:
        history = "\n".join(command_history)
        
        messages = [
            {"role": "system", "content": """
You are an expert Linux assistant. Your role is to help users with various Linux-related tasks, providing clear, accurate, and concise instructions or solutions. Here are the guidelines to follow:

1. **Understand the Query**: Identify the specific Linux-related issue or task the user needs help with.
2. **Provide Step-by-Step Instructions**: Give detailed, easy-to-follow instructions for solving the problem or performing the task.
3. **Offer Additional Tips**: Provide useful tips or best practices related to the task when applicable.
4. **Include Examples**: Where possible, include examples of commands or code snippets.
5. **Be Concise**: Keep the explanations clear and to the point to ensure the user can easily understand and follow them.

"""},
            {"role": "system", "content": history},
            {"role": "user", "content": command}
        ]
        
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            max_tokens=500,
            temperature=0.9
        )
        
        answer = response.choices[0]
        message = answer.message
        response = message.content.strip()
        command_history.append(f"{response}")
        return response
    except Exception as e:
        return f"Error handling command: {str(e)}"



class Server(paramiko.ServerInterface):
    def __init__(self):
        self.event = threading.Event()
    
    def check_channel_request(self, kind, chanid):
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
    
    def check_auth_password(self, username, password):
        #if (username == 'user') and (password == 'password'):
        return paramiko.AUTH_SUCCESSFUL
        #return paramiko.AUTH_FAILED
    
    def get_allowed_auths(self, username):
        return 'password'
    
    def check_channel_shell_request(self, channel):
        self.event.set()
        return True

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 22))
    server.listen(100)
    print("[+] Listening for connection ...")
    
    client, addr = server.accept()
    print(f"[+] Got a connection from {addr}")
    
    try:
        transport = paramiko.Transport(client)
        transport.add_server_key(HOST_KEY)
        server = Server()
        transport.start_server(server=server)
        
        channel = transport.accept(20)
        if channel is None:
            print("[-] No channel.")
            return
        
        print("[+] Authenticated!")
        server.event.wait(10)
        if not server.event.is_set():
            print("[-] Client never asked for a shell.")
            return
        
        while True:
            channel.send("$ ")
            command = ''
            while not command.endswith('\n'):
                transport = channel.recv(1024)
                command += transport.decode('utf-8')
            response = handle_command_with_gpt(command.strip())
            channel.send(response + '\n')
            if command.strip() == 'exit':
                break
        
    except Exception as e:
        print(f"[-] Caught exception: {e.__class__}: {e}")
    finally:
        client.close()

if __name__ == '__main__':
    while True:
        start_server()
