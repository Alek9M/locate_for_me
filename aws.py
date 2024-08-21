import boto3

db = dict()

def save_to_database(chat_id, username):
    db[username] = chat_id
    # dynamodb = boto3.resource('dynamodb',
    #                           region_name='us-west-2',
    #                           aws_access_key_id="YOUR ACCESS KEY",
    #                           aws_secret_access_key="YOUR SECRET KEY")
    #
    # table = dynamodb.Table('user_table')
    # table.put_item(
    #     Item={
    #         'username': username,
    #         'chat_id': chat_id
    #     }
    # )

def check_in_database(username):
    if username in db:
        return db[username]
    # dynamodb = boto3.resource('dynamodb',
    #                           region_name='us-west-2',
    #                           aws_access_key_id="YOUR ACCESS KEY",
    #                           aws_secret_access_key="YOUR SECRET KEY")
    #
    # table = dynamodb.Table('user_table')
    # response = table.get_item(
    #     Key={
    #         'username': username
    #     }
    # )
    # item = response['Item']
    # return item['chat_id'] if item else None