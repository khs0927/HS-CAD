# -*- coding: utf-8 -*-
import win32com.client
import os

def find_path():
    app = win32com.client.GetActiveObject("ZWCAD.Application.2024")
    for doc in app.Documents:
        if "drawing2" in doc.Name.lower():
            print(f"Name: {doc.Name}")
            try:
                print(f"FullName: {doc.FullName}")
            except Exception as e:
                print(f"FullName Error: {e}")
            try:
                print(f"Path: {doc.Path}")
            except Exception as e:
                print(f"Path Error: {e}")

if __name__ == "__main__":
    find_path()
