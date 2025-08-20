# Azure-Capacity-Validator-Tool
This tool validates if selected Azure Region can support planned application architecture

## Idea
User is planning to deploy or migrate application into Azure region but it's hard to validate if selected services, sku's and features are available in selected region. By using this tool user can select region, SLA needs, Availability Zone needs, Services, SKU's and all the other details and too validates if that combination is possible.

## Technical idea
* MCP server to Azure
* MCP server to Microsoft Learn Documentation
* Agents that can use internet and MCP tools to get right information
* Agents authenticate to user Azure with Read only permissions to read user specific Azure data like what's available for EA or CSP customers vs. PAYG users.
* Agents create initial plan for the project so that GitHub Copilot Coding Agent can work better
* Agents create a general baseline plan to capture all needed information
* When tool is run agents generate modified plan that matches that user session.
* Data needs to be read from Microsoft API's or documentation so that it's valid in that moment and there's no hallusination
* Tool needs to have nice modern UI where user can select Azure Services, sku's and other things that they need. This needs to be read from some Microsoft API or source so that it's valid every time user starts the session.
