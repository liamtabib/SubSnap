"""Email sending functionality."""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any

from core.config import EmailConfig
from core.constants import Constants
from formatters.email_formatter import EmailFormatter


class EmailHandler:
    """Handles email sending via SMTP."""
    
    def __init__(self, config: EmailConfig, timezone: str = 'Europe/Berlin'):
        """Initialize email sender."""
        self.config = config
        self.formatter = EmailFormatter(timezone)
    
    def send_digest(self, posts: List[Dict[str, Any]], subject: str) -> bool:
        """Send email digest with posts."""
        print(f"SMTP Email configuration:")
        print(f"- Sender: {self.config.sender}")
        print(f"- Recipient: {self.config.recipient}")
        print(f"- Password exists: {bool(self.config.password)}")
        print(f"- Password length: {len(self.config.password) if self.config.password else 0}")
        print(f"- SMTP Server: {self.config.smtp_server}")
        print(f"- SMTP Port: {self.config.smtp_port}")
        
        if not all([self.config.sender, self.config.recipient, self.config.password]):
            print("Error: Missing email configuration. Check environment variables.")
            return False
        
        # Generate email content
        html_content = self.formatter.format_html_email(posts)
        plain_text = self.formatter.format_plain_text_email(posts)
        
        # Create message
        message = MIMEMultipart()
        message["Subject"] = subject
        message["From"] = self.config.sender
        message["To"] = self.config.recipient
        message["MIME-Version"] = "1.0"
        
        # Create MIME parts
        html_part = MIMEText(html_content, "html")
        text_part = MIMEText(plain_text, "plain")
        
        # Create multipart/alternative
        alternative = MIMEMultipart("alternative")
        alternative.attach(text_part)
        alternative.attach(html_part)
        
        # Attach to message
        message.attach(alternative)
        
        # Send email
        try:
            print("Attempting to connect to SMTP server...")
            
            # First try with TLS
            try:
                print("Trying STARTTLS method...")
                context = ssl.create_default_context()
                with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port, 
                                timeout=Constants.SMTP_TIMEOUT) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    print("Login to SMTP server...")
                    server.login(self.config.sender, self.config.password.strip())
                    print("Sending email...")
                    server.sendmail(self.config.sender, self.config.recipient, message.as_string())
                    print(f"Email sent successfully to {self.config.recipient}")
                    return True
                    
            except Exception as tls_error:
                print(f"TLS method failed: {tls_error}")
                
                # If TLS fails, try SSL
                try:
                    print("Trying SSL method...")
                    with smtplib.SMTP_SSL(self.config.smtp_server, 465, 
                                        timeout=Constants.SMTP_TIMEOUT) as server:
                        server.ehlo()
                        server.login(self.config.sender, self.config.password.strip())
                        server.sendmail(self.config.sender, self.config.recipient, message.as_string())
                        print(f"Email sent successfully to {self.config.recipient} (using SSL)")
                        return True
                        
                except Exception as ssl_error:
                    raise Exception(f"Both TLS and SSL methods failed. TLS error: {tls_error}, SSL error: {ssl_error}")
                    
        except Exception as e:
            print(f"Failed to send email: {e}")
            print("Check your app password and make sure it doesn't have spaces.")
            print("Also verify that 'Less secure app access' is enabled or you're using an App Password.")
            return False