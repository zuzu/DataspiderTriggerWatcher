# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import requests
import cgi
import os.path
import sys
import os
import subprocess
import xml.etree.ElementTree as ET
from git import Repo
from datetime import datetime


def parser():
    usage = 'Usage: python {} folderPath extractPath [--help]'\
            .format(__file__)
    arguments = sys.argv
    if len(arguments) == 1:
        print(usage)
        sys.exit(-1)
    # ファイル自身を指す最初の引数を除去
    arguments.pop(0)
    # 引数
    folderPath = arguments[0]
    if folderPath.startswith('-'):
        print(usage)
        sys.exit(-1)
    # - で始まるoption
    options = [option for option in arguments if option.startswith('-')]

    if '-h' in options or '--help' in options:
        print(usage)
        sys.exit(-1)

    return folderPath

def diffPrint(diff, baseFolder):

    # 変数初期化
    returnMessage = ''
    triggerName = triggerType = statusMes = projectName = modified = modifier = ''

    try:
        filePath = os.path.join(baseFolder, diff.b_path.replace('/', os.sep).replace('"', ''))

        if diff.b_path.find("trigger") == -1 and len(diff.b_path.split('/')) < 3:
            return ''

        triggerName = diff.b_path.split('/')[-1]
        triggerType = diff.b_path.split('/')[-2]
        rootElem  = ET.parse(filePath).getroot()
        statusMes = '有効' if rootElem.findtext(".//status") == '1'\
                    else '無効' if rootElem.findtext(".//status") == '2' else '不明'
        projectName = rootElem.findtext(".//projectName")
        modified = rootElem.findtext(".//modified")
        if modified == '0':
            modified = rootElem.findtext(".//created")
        modified = datetime.fromtimestamp(int(modified[0:10])).strftime("%Y/%m/%d %H:%M:%S")

        modifier = rootElem.findtext(".//modifier")
    except:
        import traceback
        returnMessage += '下記トリガー解析中にエラーが発生しました。' + traceback.format_exc() + "\n"

    returnMessage += ' *[' + statusMes + ']' + triggerName + "\n"
    returnMessage += '  トリガー種別: ' + triggerType+ "\n"
    returnMessage += '  プロジェクト名: ' + projectName+ "\n"
    returnMessage += '  編集日時: ' + modified+ "\n"
    returnMessage += '  編集ユーザー: ' + modifier+ "\n"

    return returnMessage
    
if __name__ == '__main__':
    folderPath = parser().replace('/', os.sep)

    # authenticity_tokenの取得
    s = requests.Session()
    r = s.get('http://XXX.XXX.XXX.XXX:7700/WebConsole/login.do')
    soup = BeautifulSoup(r.text, "lxml-xml")
    loginPath = soup.find('form').get('action')
    # auth_token = soup.find(attrs={'name': 'authenticity_token'}).get('value')
    # payload['authenticity_token'] = auth_token

    # ログイン
    payload = {
        'user': 'XXX',
        'password': 'XXX'
    }
    r = s.post('http://XXX.XXX.XXX.XXX:7700' + loginPath, data=payload)
    #print(r.text)

    # ダウンロード
    payload = {
        'trigger': 'true',
        'triggerEnabledValue': 'true'
    }
    r = s.post('http://XXX.XXX.XXX.XXX:7700/WebConsole/export.do', data=payload, stream=True)
    local_filename = cgi.parse_header(r.headers['Content-Disposition'])[-1]['filename']
    filePath = os.path.join(folderPath, local_filename)

    # ダウンロード処理
    with open(filePath, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)

    # ZIP解凍
    FNULL = open(os.devnull, 'w')
    popen = subprocess.Popen('dataspider_trigger_backup_extract.bat ' + filePath + ' ' + folderPath, shell=True, stdout=FNULL, stderr=subprocess.STDOUT)
    popen.wait()
    # Python内でZIPを解凍するより7z.exeなど外部コマンドのほうが早かった。
    ## dataspider_trigger_backup_extract.bat
    #### "C:\Program Files\7-Zip\7z.exe" x -y %1 -o%~2 -xr!*.class
    #### xcopy /e %~2\%~n1\* %~2
    #### rmdir /s /q %~2\%~n1\
    #### del /Q %1

    # Git
    try:
        repo = Repo(folderPath)
        repo.git.add('--all')

        if len(repo.index.diff(repo.head.commit)) == 0 :
            print("トリガーに変更がありませんでした。")
        else :
            repo.git.commit(m='Automatically commit.')
            repo.git.push("origin", "HEAD:refs/heads/master")
            
            # コミットの一覧を取得
            commits_list = list(repo.iter_commits())
            
            # 最新のコミットとそのひとつ前のコミットを比較する。
            outputMessage = ""
            outputMessage += '■新規追加されたトリガー\n'
            for diffItem in commits_list[1].diff(commits_list[0]).iter_change_type('A'):
                outputMessage += diffPrint(diffItem, folderPath)
            
            outputMessage += "\n"
            
            outputMessage += '■削除されたトリガー\n'
            for diffItem in commits_list[1].diff(commits_list[0]).iter_change_type('D'):
                outputMessage += diffPrint(diffItem, folderPath)
            
            outputMessage += "\n"
            
            outputMessage += '■変更されたトリガー\n'
            for diffItem in commits_list[1].diff(commits_list[0]).iter_change_type('M'):
                outputMessage += diffPrint(diffItem, folderPath)
            
            outputMessage += "\n"
            print(outputMessage)

    except:
        print('■エラー発生')
        import traceback
        traceback.print_exc()
        sys.exit(-1)

    sys.exit()
