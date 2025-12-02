import requests

files = [('files', open('E:/Music/Common Songs/06-MD-feat.-Niska.mp3','rb'))]
data = {'text': 'Hello from python'}

res = requests.post("http://localhost/post/add", data=data, files=files)
print(res.json())
