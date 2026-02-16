import socket


def get_ip_address():
    # функция для получения автоматического получения ip сервера
     
    try:
        # Способ 1: через подключение к внешнему серверу
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:

        # Способ 2: через hostname
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        return ip


ip = get_ip_address()

port = 3000

origins = [
    f'http://localhost:{port}',
    f'http://127.0.0.1:{port}',
    f'http://{ip}:3000' 
]
