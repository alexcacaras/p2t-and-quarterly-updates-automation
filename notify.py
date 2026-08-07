import smtplib
from email.message import EmailMessage
from crypto_env import load_env_from_encrypted, get_env, _get_env_prefix # dotenv for loading env variables from .env file into python but from the encypted version
load_env_from_encrypted()   # load .env before reading env vars from encrypted version
ENV_PREFIX = _get_env_prefix()

SMTP_HOST = get_env('SMTP_HOST')
EMAIL_PORT = int(get_env('EMAIL_PORT'))
EMAIL_PASSWORD = get_env('EMAIL_PASSWORD')
EMAIL_RECIPIENT = get_env('EMAIL_RECIPIENT')
EMAIL_SENDER = get_env('EMAIL_SENDER')

def send_notification(subject, body):
    # Set up SMTP connection to Gmail's SMTP server
    mail = smtplib.SMTP(SMTP_HOST, EMAIL_PORT)
    # Identify yourself to the SMTP server
    mail.ehlo()  
    # Start TLS encryption for the connection
    mail.starttls()  

    # Gmail account credentials 
    sender = EMAIL_SENDER
    password = EMAIL_PASSWORD

    # Login to Gmail's SMTP server
    mail.login(sender, password)

    recipient = EMAIL_RECIPIENT
    
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)

    # Send email
    mail.send_message(msg)

    # Close SMTP connection
    mail.quit()

if __name__ == "__main__":
    send_notification("Test Email", "Hello World")