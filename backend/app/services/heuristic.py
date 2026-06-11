import re
import time
from bs4 import BeautifulSoup

# Define Blacklists
SPAM_DOMAINS = {
    "marketing-guru.io", 
    "spammy-outreach.com", 
    "coldoutreach.com", 
    "wealth-transfer.com"
}

SPAM_KEYWORDS = [
    r"front page of google", 
    r"nigerian prince", 
    r"inheritance of", 
    r"claim your share", 
    r"boost your seo",
    r"collab opportunity",
    r"make \$?50,?000,?000",
    r"click here to claim"
]

URGENT_KEYWORDS = [
    r"\burgent\b", 
    r"\bp0\b", 
    r"\boutage\b", 
    r"system down", 
    r"losing money", 
    r"cease and desist",
    r"legal action", 
    r"lawsuit", 
    r"ransomware", 
    r"security breach", 
    r"data breach"
]

SECURITY_KEYWORDS = [
    r"suspicious login",
    r"data breach",
    r"ransomware",
    r"credential theft",
    r"malware",
    r"send \d+ btc",
    r"publish the data",
    r"wallet \w+",
    r"unauthorized access",
    r"hacker"
]

INTERNAL_DOMAINS = {
    "internal.com",
    "mycompany.com",
    "ourplatform.com"
}

def clean_body(body: str) -> str:
    """
    Cleans body of HTML entities or tags and returns stripped plaintext.
    """
    if not body:
        return ""
    # Strip HTML tags using BeautifulSoup
    try:
        soup = BeautifulSoup(body, "html.parser")
        text = soup.get_text()
    except Exception:
        # Fallback regex if BeautifulSoup fails
        text = re.sub(r'<[^>]+>', '', body)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def analyze_heuristics(sender: str, subject: str, body: str) -> dict:
    """
    Synchronous fast analysis of email. Target execution is < 10ms.
    """
    start_time = time.perf_counter()
    
    subject_lower = (subject or "").lower()
    body_clean = clean_body(body)
    body_lower = body_clean.lower()
    
    # Extract domain
    domain = ""
    if "@" in sender:
        domain = sender.split("@")[-1].lower()
        
    # 1. Internal Email Detection
    is_internal = domain in INTERNAL_DOMAINS or sender.endswith("@internal.com") or sender.endswith("@mycompany.com")
    
    # 2. Spam Detection
    is_spam = False
    if domain in SPAM_DOMAINS:
        is_spam = True
    else:
        # Check spam keywords
        for kw in SPAM_KEYWORDS:
            if re.search(kw, subject_lower) or re.search(kw, body_lower):
                is_spam = True
                break
                
    # 3. Security Detection
    is_security = False
    for kw in SECURITY_KEYWORDS:
        if re.search(kw, subject_lower) or re.search(kw, body_lower):
            is_security = True
            break
            
    # 4. Urgency Detection
    urgency = "Low"
    is_urgent = False
    for kw in URGENT_KEYWORDS:
        if re.search(kw, subject_lower) or re.search(kw, body_lower):
            is_urgent = True
            break
            
    if is_security:
        urgency = "Critical"
    elif is_urgent:
        urgency = "Critical" if "p0" in subject_lower or "outage" in subject_lower or "cease and desist" in subject_lower else "High"
    elif is_internal:
        urgency = "Low"
    else:
        # check basic prompt urgencies
        if "asap" in body_lower or "immediate" in body_lower:
            urgency = "Medium"

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    return {
        "is_internal": is_internal,
        "is_spam": is_spam,
        "is_security": is_security,
        "urgency": urgency,
        "elapsed_ms": round(elapsed_ms, 3),
        "cleaned_body": body_clean
    }
