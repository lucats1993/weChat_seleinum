import pymongo
import os
import subprocess

bin_path =r"C:\Program Files\MongoDB\Server\4.0\bin"
mongo =os.path.join(bin_path,"mongo.exe")
update_js =os.path.join(bin_path,"update.js")
cmd = '"' + mongo + '" ../script/update.js'
# return_code = subprocess.call(,shell=True)
return_code =subprocess.call(cmd, shell = True)
# print(return_code)

