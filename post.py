import requests

files = [('files', open('E:/Videos/0408(1).mp4','rb'))]
data = {'text': 'Hello fuck you"'}

res = requests.post("http://localhost/post/add", data=data, files=files)
print(res.json())
