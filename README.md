<!-- <img src="https://github.com/catherineisonline/advice-generator-app-frontendmentor/blob/main/images/project-preview.png?raw=true"></img> -->

<h1 align="center">Ecommerce Price Optimizer</h1>

<div align="center">
   Web scrapping of competitors catalog publication prices via MercadoLibre API and updating price dynamically following business rules based on schedules, time winning and minimum prices with AWS Lambda.
</div>
<br>

## About The Project

<p>A simple project if you're learning how to interact with 3rd-party APIs. This project uses the Mercado Libre API to scrape the user products and
its competitors publications. The purpose is to build an optimization algorithm that updates the prices of the user catalog publications based on the competitors 
prices in order to obtain the "Winner" status in each corresponding publication as long as possible during the day. The solution followed a free tier approach, trying not to exceed free quotas of different services like Google Sheet API, Lambda, etc.
<p>
   
<br>
Users should be able to: <br>
<br>
1. Automatically execute a price update following business rules such as being below or above certain competitor price, based on a fixed amount or percentage of the competitor price.
<br>
2. Obtain event logs for each result of the optimizer of each publication in order to know if the user won the publication, at what cost and the reasons.
<br>
3. Modify manually in a Google Spreadsheet the parameters of the optimizer.
<br>
4. Analyze time ranges with more difficulty to win publications and competitors behaviours.
<br> 
5. Test and pause the optimizer via AWS Lambda console.
<br>
6. Use minimum price of different stock batches when a certain level of stock is reached.
<br>
7. Execute the optimizer in more than one Mercado Libre account.
<br>
8. Add new publications to follow its performance and optimize its price.
<br>

## Files

This project contains source code and supporting files for a serverless application that you can deploy with the SAM CLI. It includes the following files and folders.

- data_producer - Code for the application's Lambda function and Project Dockerfile.
- Makefile - Automating software building procedure and other tasks with dependencies.
- tests - Unit tests for the application code. 
- template.yaml - A template that defines the application's AWS resources. There is no events folder as the event is defined as a cron schedule in the template.yaml
- buildspec.yaml - Github Actions workflow for installing dependencies, linting, testing and formatting code. 

## Built with 

- IDE: Visual Studio Code
- Programming Language: Python 3.10
- Docker
- Postman
- Github
- AWS Secrets Manager, Elastic Container Registry, Lambda, EventBridge, OpenSearch and S3.
- AWS SAM (Necessesary to run and deploy)


## Useful resources

1. <a href="https://developers.mercadolibre.com.ar/devcenter">MercadoLibre Dev Center</a> - Ecommerce developer website for built in apps.
2. <a href="https://developers.mercadolibre.com.ar/es_ar/api-docs-es">MercadoLibre API Docs</a> - API Endpoints, code snippets, quickstart guide, auth guide and example responses.
3. <a href="https://docs.docker.com/get-started/">Docker Documentation</a> - Getting Started, etc.
4. <a href="https://docs.aws.amazon.com/lambda/latest/dg/python-package.html#python-package-create-dependencies">AWS Lambda Documentation</a> - To create the deployment package (virtual environment).
5. <a href="https://stackoverflow.com/questions/68206078/how-to-use-dependencies-in-sam-local-environment"> Dependencies in SAM</a> - Running a function with library and module imports locally.
6. <a href="https://www.youtube.com/watch?v=jXjMrWCpaI8&ab_channel=FelixYu">AWS Lambda Layers Introduction</a> - Instruction on how to create lambda layers with pandas and requests using docker.
7. <a href="https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-invoke.html">AWS Serverless SAM CLI</a> - Serverless SAM CLI using invoke.
8. <a href="https://aws.amazon.com/es/free/?all-free-tier.sort-by=item.additionalFields.SortRank&all-free-tier.sort-order=asc&awsf.Free%20Tier%20Types=*all&awsf.Free%20Tier%20Categories=*all">AWS Pricing</a> - AWS Free Tier for costs calculation.
9. <a href="https://developers.google.com/sheets/api/limits?hl=es-419">Google API Limits</a> - Google Free Tier for costs calculation.
10. <a href="https://crontab.guru">Crontab guru</a> - Quick and simple editor for cron schedule expressions.
11. <a href="https://www.elastic.co/guide/en/elasticsearch/reference/current/text.html#fielddata-mapping-param">ElasticSearch Doc</a> - Mapping documentation for ElasticSearch.
   
## Previous steps and installations needed

1. Install Visual Studio Code
2. Install Python 3.10
3. Install libraries used
4. Install AWS CLI
5. Install Docker
6. Install WSL
7. Install Ubuntu
8. Create a Service Account in Google
9. Download Google Sheets API credentials
10. Store Google Sheets API credentials on AWS Secrets Manager
11. Share Google Spreadsheet with the Google Service Account email
12. Create a AWS Lambda Function via AWS CLI with CloudFormation

## Difficulties found and learnings:

1. The PUT requests of the price update were instantly, but the impact on the status of competing in the publication had a delay of ~5 minutes, so the optimizer should sleep for 5 minutes in order to execute again and check the status on the publication with the new price. Besides, the lambda function has a timeout of 15 minutes, so the optimizer could not exceed 3 loops. The code was changed to run just one iteration on checking and updating the price and the frequency of the lambda function was increased, instead of having an unnecessary sleep in the code.
2. AWS Lambda function supports up to 50 MB of size for the option of dropping a zip file with the lambda_hanlder file and extra files desired. As my dependencies installed had a superior size of 50 MB I found two possible options to overcome this:
- Upload the zip file with the dependencies package and the lambda_function.py in an S3 bucket and then linked the lambda code to the S3 bucket URL. This option allows up to 250 Mb of unzipped files.
- This solution appeared when the previous solution became useless when I tried to install new libraries and summed a total of more than 250 Mb of unzipped files. You can create a deployment package with the dependencies and the lambda function code in a container image and create a lambda function from a container image. In this case you will need to create a repository in Elastic Container Registry (ECR), create an image with Docker and push the image with AWS CLI. This option lets you upload up to 10 GB unzipped files.
  
4. Be sure to be creating the AWS Lambda function in the same time zone, the same operating system environment (runtime) and programming language version that the AWS Secrets Manager and Eventbirdge are configured in.
5. Installing libraries in a Windows environment brought a constant problem of module imports in the python file that made they were not recognized when deploying it in AWS.

- I could have solved the module imports problem by running a docker container of AmazonLinux in my IDE (Docker must be opened in the computer) but the problem was that by default the libraries were installed in python3.7 and my code was written in python3.9, so one solution could have been adapting my code to python3.7. I could not install a newer version of python in the docker container because I did not have the Unix native command "sudo" for installations.
- I tried to run a AmazonLinux2 in EC2 instance with PuTTY in my computer with Windows (had to create a key file .ppm and give access in IAM to EC2) and have no success neither.
- The solution I found was to install a Linux environment and run my libraries installations in a virtual environment in Ubuntu. With Ubuntu I could run the sudo apt command and zip -r to create the deployment package in a zip file with libraries installed in Linux.

## Costs considerations

1. Google API has a limit of 60 API calls per minute (for each writing and reading), so in order to avoid exceeding the rate, I needed a rate limiting when reading parameters from the Google Sheets and writing cells for the logs. I solved the rate limiting with a “Exponential backoff retry” algorithm from the APIError module of Gspread library and with a Time-to-live cache limiting (TTL Cache).
2. AWS Secrets Manager charges you 0,4 USD/month for each pair of key-secret stored in the vault.
3. Lambda is free below the 1 million calls per month. The client has a cost calculator that shows how many publications can be scrapped with the defined frequency of executing of the lambda in order to keep the free quota of Lambda. Once exceeded, Lambda charges you 0,0000002 USD for each additional call.
4. S3 lets you stored files up to 5 GB during 12 months for free.
5. OpenSearch free tier is able for a t2.small or t3.small instance in a single Availability Zone (AZ) up to 750 hours of use per month and a EBS (Elastic Block Storage) volume of 10 GB per month.

## Getting started

**Mercado Libre App:**
1. Log in with your account on https://developers.mercadolibre.com.ar/devcenter and create an application. You will need a logo photo and a redirect URL for your app.
2. In the configuration you should select all API scopes desired to access with that account. Select read, offline access and write.
3. Once created, enter to the app and copy the App ID and Client Secret. This values will be used to generate an access token to make calls to the Mercado Libre API.
4. In a browser enter the following URL replacing the value with your app ID and URL: https://auth.mercadolibre.com.ar/authorization?response_type=code&client_id={YOUR_APP_ID}&redirect_uri={YOUR_APP_URL}.
5. The browser should redirect you to the website of the URL, in the search bar a new URL is generated, you should copy the code that follows the "TG". This code is a refresh token that expires every 6 hours and you can generate with an API call. The refresh token is needed to generate an access token that expires with the refresh token. So when 6 hours have passed, you need to generate both, refresh token and access token.

**Create a deployment package of dependencies in Ubuntu:**
1. Initialize Ubuntu with the command "Ubuntu". Then install python version of your lambda function and pip.
2. Locate your directory with the python file and create a venv to install libraries. To locate your python lambda file that is in your PC you need to change directory (cd..) until you get to the "/" directory. Check the directory with "pwd" command. Once in "/" directory, do a "ls" to list the items in that directory. You should go to "mnt", your disk ("c" in my case), Users, your PC user and then go to the directory where you have your python file.
3. For the creation of the virutal environment (Ubuntu):
- python3 -m venv venv
- source source ./venv/bin/activate (venv/Scripts/activate on Windows)
- install -r requirements.txt
- cd venv/lib/python3.10/site-packages
- deactivate
- zip -r ../../../deployment_package.zip .

**Build and deploy a container image in ECR**:
1. Ensure you have create an access key in your IAM user. Copy the access key and secret access key.
2. Execute 'aws configure' in order to log in to your AWS account entering the access key, secret access key and aws region.
3. Create the requirements.txt file with the python packages names and versions (optional).
4. Create the lambda_function.py at folder level.
5. Create the lambda-image.dockerfile with the following instructions:
```
FROM public.ecr.aws/lambda/python:3.10

COPY requirements.txt ./
RUN python3.10 -m pip install -r requirements.txt -t .

COPY lambda_function.py ./

CMD ["lambda_function.lambda_handler"]
```
6. Execute the following commands, replacing with you image name, aws region, dockerfile name, tag name and ECR repository URI:
```
aws ecr get-login-password --region <your-aws-region> | docker login --username AWS --password-stdin <your-ECR-repo-URI>
docker build -t <your-image-name> -f <your-dockerfile-name>.dockerfile .
docker tag <your-image-name>:<your-tag-name> <your-ECR-repo-URI>:<your-tag-name>
docker push  <your-ECR-repo-URI>:<your-tag-name>
```

**To build and deploy your application for the first time, run the following in your shell:**
```bash
sam build
sam deploy --guided
```

**Run functions locally and invoke them:**
```bash
folder-name-containing-files$ sam local invoke Function --event events/event.json
```

**Create a OpenSearch Dashboard:**

1. Create a domain in Amazon OpenSearch Service.
2. Create a username and password for the URL endpoint.
3. Enter to the OpenSearch Dashboards URL (IPv4).
4. Create an index on the Index Management/Index tab or make a POST request with option 5.
5. Go to Interact with the OpenSearch API and update the index data schema (aka "mapping") of your data being inputed:
```JSON
PUT /your-index-name
{
  "mappings": {
    "properties": {
      "update_date": {
        "type": "date"
      },
      "free_shipping": {
        "type": "boolean"
      },
      "API_calls": {
        "type": "integer"
      },
      "initial_price": {
        "type": "float"
      "product_name": {
        "type": "text"
      },
      "stock": {
        "type": "integer"
      },
      "time": {
        "type": "float"
      }
    }
  }
}
```

If your string field has spaces in between, this is, not a continuous string, you should use the type "keyword" in order to use the string as it is and avoid getting the string splitted. Check: https://discuss.elastic.co/t/fields-not-displaying-in-visualize/133501.

5. Create an index pattern on the Dashboard Management/Index patterns tab.
6. Go to Visualize tab, choose a visual and find the Index pattern you created to use as your data input.

**IAM policies needed**:
1. Secrets Manager Read and Write secret keys: attach a policy of ReadWrite for the Lambda role in order to access the SecretsManager service and retrieve the secrets values.
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue",
                "kms:Decrypt"
            ],
            "Resource": [
                "arn:aws:secretsmanager:<your-aws-region>:<your-aws-account-id>:secret:<your-first-secret-name>",
                "arn:aws:secretsmanager:<your-aws-region>:<your-aws-account-id>:secret:<your-second-secret-name>"
            ]
        }
    ]
}
```
2. ECR Put and Get images: create and attach a inline policy with the following JSON for the Lambda role to be able to get images of the ECR repo:

```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ecr:GetDownloadUrlForLayer",
                "ecr:GetAuthorizationToken",
                "ecr:BatchCheckLayerAvailability",
                "ecr:BatchGetImage",
                "ecr:GetRepositoryPolicy",
                "ecr:ListImages",
                "ecr:PutImage",
                "ecr:DescribeImages",
                "ecr:DescribeRepositories",
                "ecr:GetLifecyclePolicyPreview",
                "ecr:GetLifecyclePolicy"
            ],
            "Resource": "arn:aws:ecr:<your-aws-region>:<your-aws-account-id>:repository/<your-ecr-repo-name>"
        }
    ]
}
```
3. OpenSearch Get and Put documents:
```
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "es:ESHttpGet",
                "es:ESHttpPut",
                "es:ESHttpHead",
                "es:ESHttpGet"
            ],
            "Resource": "arn:aws:es:<your-aws-region>:<your-aws-account-id>:domain/<your-domain-name>"
        }
    ]
}
```

## TL/DR

The python code of the lambda function is containerized with its dependencies in a docker image, pushed to ECR and attached to the Lambda function. The lambda function is executed by an EventBridge trigger every X minutes predefined on AWS console.

## Acknowledgments

Matias Kahnlein - Caylent DevOps
