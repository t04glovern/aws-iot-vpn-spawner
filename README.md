# AWS IoT Button VPN Spawner

In this repo we deploy a pipeline to spin up new VPN's at a push of a Button... Literally.

We also deploy and connect our AWS IoT Button via the Certificate Vending machine. This allows for it to be managed as a device in a more unified way.

## Setup Repo

Pull down the repository locally to start with

```bash
git clone https://github.com/t04glovern/aws-iot-vpn-spawner.git
```

We utilize [aws-pptp-cloudformation](https://github.com/t04glovern/aws-pptp-cloudformation) and therefore need to init the submodule in the project to use it.

```bash
git submodule init
```

## IoT Certificate Vending Machine

We need to deploy the [IoT Certificate vending machine](https://github.com/awslabs/aws-iot-certificate-vending-machine) lambda code somewhere accessible for CloudFormation.

```bash
## The command I use to deploy the IoT CVM code to my bucket
aws s3 cp aws-iot-cvm/iot-cvm.zip s3://devopstar/resources/aws-iot-vpn-spawner/iot-cvm.zip
```

This reference must be updated in the `aws-iot-cvm/iot-cvm-params.json` parameters file else it will default to the version in my bucket. This is only applicable if you'd prefer to deploy your own.

```bash
{
    "ParameterKey": "LambdaCodeBucket",
    "ParameterValue": "devopstar" # Bucket Name
},
{
    "ParameterKey": "LambdaCodeS3Key",
    "ParameterValue": "resources/aws-iot-vpn-spawner/iot-cvm.zip" # Code Location
}
```

Deploys a IoT Vending machine instances that can be used to generate certificates for new devices

```bash
aws cloudformation create-stack --stack-name "devopstar-iot-cvm" \
    --template-body file://aws-iot-cvm/iot-cvm.yaml \
    --parameters file://aws-iot-cvm/iot-cvm-params.json \
    --capabilities CAPABILITY_IAM
```

Get details, including your API Endpoint for adding new IoT devices

```bash
aws cloudformation describe-stacks --stack-name "devopstar-iot-cvm" \
    --query 'Stacks[0].Outputs[?OutputKey==`RequestUrlExample`].OutputValue' \
    --output text

# https://xxxxxxxx.execute-api.us-east-1.amazonaws.com/LATEST/getcert?serialNumber=value1&deviceToken=value2
```

Create a new Item in DynamoDB for your device by replacing:

* **devopstar-iot-btn-01**: With your desired name for the device / button
* **secret_key**: Something secret :)

```bash
aws dynamodb put-item \
    --table-name iot-cvm-device-info \
    --item '{"deviceToken":{"S":"secret_key"},"serialNumber":{"S":"devopstar-iot-btn-01"}}'
```

Now make a request with the URL you got from the API gateway. Save the results to a file `config/iot-key.json`

```bash
https://xxxxxxxx.execute-api.us-east-1.amazonaws.com/LATEST/getcert?serialNumber=devopstar-iot-btn-01&deviceToken=secret_key
```

You'll be returned a json response:

```json
{
    "certificateArn": "arn:aws:iot:us-east-1:<account-id>:cert/009ff6ee0.........",
    "certificateId": "009ff6ee092e......",
    "certificatePem": "-----BEGIN CERTIFICATE-----\nMIIDWTCCAkGgAwIBAgIUZiIgLi......-----END CERTIFICATE-----\n",
    "keyPair": {
        "PublicKey": "-----BEGIN PUBLIC KEY-----\nMIIBIjANBgkqhkiG9w0BAQEFAAO.......-----END PUBLIC KEY-----\n",
        "PrivateKey": "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQ........-----END RSA PRIVATE KEY-----\n"
    },
    "RootCA": "-----BEGIN CERTIFICATE-----\r\nMIIE0zCCA7ugAwIBAgIQGNrRniZ96Lt........-----END CERTIFICATE-----"
}
```

Place the outputs for each of the two fields below into new files in [config/](config/)

* **config/iot-certificate.pem.crt**: certificatePem
* **config/iot-private.pem.key**: keyPair.PrivateKey

*Annoyingly you'll have to remove the newline delimiters with actual newlines. I usually use a `\\n` -> `\n` regular expression find and replace in VSCode*

## AWS IoT Button Configure

Hold the button down on your IoT Button for 5+ seconds until the blue light starts blinking. Connect to the WiFi Host-spot that your Button starts broadcasting

It should have an SSID like: `Button ConfigureME - GE3`. The Password is the last 8 digits of your DSN (on the back of the button or on the box it came in).

### Web Interface

Navigate to 192.168.0.1 in your browser and fill out the details.

You can retrieve your endpoint under the [Settings > Custom Endpoint section of AWS IoT](https://console.aws.amazon.com/iot/home?region=us-east-1#/settings)

### Programmatic Approach (Unreliable, but works if you have the correct boundary)

Make a copy of the `config/iot-setup-example.cfg` file to `config/iot-setup.cfg`. Go through and replace:

* **wifi_ssid** *(Line 4)* - Your WiFi SSID
* **wifi_password** *(Line 8)* - Your WiFi PASS
* **aws_iot_certificate** *(Line 13-32)* - Your config/iot-certificate.pem.crt contents
* **aws_iot_private_key** *(Line 38-64)* - Your config/iot-private.pem.key contents
* **endpoint_region** *(Line 69)* - Your Endpoint Region (e.g. us-east-1)
* **endpoint_subdomain** *(Line 73)* - Your Endpoint Subdomain (get from IoT settings)

```bash
curl \
    -X POST \
    -H "Content-Type: multipart/form-data; boundary=---------------------------3227789394019354511493055142" \
    -F file=@config/iot-setup.cfg \
    http://192.168.0.1/configure
```

## AWS IoT Action Rule Deploy

We'll start by pushing our stack-builder.zip and pptp-server.yaml files to an S3 bucket that CloudFormation can access.

```bash
# Package Lambda
cd aws-iot-action && ./package-lambda.sh && ../

# Push Lambda to S3
aws s3 cp aws-iot-action/stack-builder.zip s3://devopstar/resources/aws-iot-vpn-spawner/stack-builder.zip

# Upload copy of PPTP yaml
aws s3 cp aws-pptp-cloudformation/pptp-server.yaml s3://devopstar/resources/aws-iot-vpn-spawner/pptp-server.yaml
```

Make sure you edit your `aws-iot-action/iot-rule-params.json` to include your S3 paths if you aren't using mine. You also need to make sure you update your `IoTButtonTopic` parameter so that it matches your device ID (found on the back of the button). The `VPNSubscriber` should be set to your email address that you want to receive notifications to about your newly created VPN.

```bash
aws cloudformation create-stack --stack-name "devopstar-iot-rule" \
    --template-body file://aws-iot-action/iot-rule.yaml \
    --parameters file://aws-iot-action/iot-rule-params.json \
    --capabilities CAPABILITY_IAM
```
