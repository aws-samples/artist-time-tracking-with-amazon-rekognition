# Computing Artist Time on Screen with Amazon Rekognition

This package includes a sample workflow that uses Amazon Rekognition to detect artists in a video and compute the total time they appear on screen.

All resources are defined in an AWS SAM template, an extension of AWS CloudFormation. AWS CloudFormation lets you model, provision, and manage AWS and third-party resources by treating infrastructure as code. During deployment, SAM transforms and expands the SAM syntax into AWS CloudFormation syntax. Then, CloudFormation provisions your resources.

## Deployment prerequisites

* AWS CLI. Refer to [Installing the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html)
* AWS Credentials configured in your environment. Refer to [Configuration and credential file settings](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
* AWS SAM CLI. Refer to [Installing the AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
* Docker. Refer to [Install Docker Engine](https://docs.docker.com/engine/install/)

## Deployment instructions

Run the command below to deploy the resources in your AWS account:

```sh
sam build --use-container && sam deploy --guided
```

Follow the prompts.

When asked for the region value, choose `us-east-1`.

> **IMPORTANT!** The CloudFormation template includes a resource configured to run in the `us-east-1` region. If you want to create the stack in another region, remove the `CloudFrontWebACL` resource (currently not supported in other regions) from the `template.yaml` file.

You'll also need to provide values for some CloudFormation template parameters:

- `DataBucketName`: the name of the S3 bucket in which episodes and faces are stored

> Note that S3 Bucket names must be unique across all AWS Accounts and all AWS Regions. For more information refer to [Bucket naming rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/bucketnamingrules.html).

## Clean up

If you don't want to continue using this solution, clean up its resources to avoid further charges. To delete everything, you need to delete the AWS CloudFormation stack, the Amazon S3 buckets, and the Amazon DynamoDB tables.

### AWS CloudFormation stack

Deleting the AWS CloudFormation stack will delete the underlying resources created, except Amazon S3 buckets and Amazon DynamoDB tables. Follow the steps below to delete the AWS CloudFormation stack.

1. Sign in to the [AWS CloudFormation console](https://console.aws.amazon.com/cloudformation).
2. On the **Stacks** page, select the stack.
3. Choose **Delete**.

### Amazon S3 buckets

After deleting the stack, you must manually delete the S3 buckets if you do not want to retain the data. Follow these steps to delete the Amazon S3 buckets.

1. Sign in to the [Amazon S3 console](https://console.aws.amazon.com/s3).
2. Choose **Buckets** from the left navigation pane.
3. Locate the `<stack-name>-loggingbucket-*` S3 bucket.
4. Select the S3 bucket and choose **Delete**.
5. Locate the `<stack-name>-staticwebsitebucket-*` S3 bucket.
6. Select the S3 bucket and choose **Delete**.
7. Locate the `<DataBucketName>` S3 bucket.
8. Select the S3 bucket and choose **Delete**.

### Amazon DynamoDB tables

After deleting the stack, you must manually delete the Amazon DynamoDB tables if you do not want to retain the data.

Follow these steps to delete the Amazon DynamoDB tables:

1. Sign in to the [Amazon DynamoDB console](https://console.aws.amazon.com/dynamodb).
2. Choose **Tables** from the left navigation pane.
3. Locate the `<stack-name>-CollectionsTable-*`, `<stack-name>-FacesTable-*`, `<stack-name>-JobsTable-*`,
   and `<stack-name>-ResultsTable-*` tables.
4. Select the tables and choose **Delete**.

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
