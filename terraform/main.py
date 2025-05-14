#!/usr/bin/env python
from constructs import Construct
from cdktf import App, TerraformStack


class MyStack(TerraformStack):
    def __init__(self, scope: Construct, id: str):
        super().__init__(scope, id)

        # define resources here
        
        #change "app" in cdktf.json to deploy main_serverless first then main_server 


app = App()
MyStack(app, "ter")

app.synth()
