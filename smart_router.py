# Keywords jo complex tasks indicate karte hain (Cloud bhejna chahiye)
COMPLEX_KEYWORDS = [
    'explain', 'analyze', 'compare', 'debug', 'code', 'function', 'algorithm',
    'math', 'calculate', 'equation', 'detailed', 'comprehensive', 'step-by-step',
    'complex', 'advanced', 'expert', 'professional', 'write a script', 'python'
]

# Keywords jo simple tasks indicate karte hain (Local bhejna chahiye)
SIMPLE_KEYWORDS = [
    'hi', 'hello', 'hey', 'thanks', 'ok', 'yes', 'no', 'good', 'bye',
    'what is', 'who is', 'summarize'
]

def analyze_intent(prompt: str) -> dict:
    """Analyze prompt complexity based on keywords and structure"""
    prompt_lower = prompt.lower()
    word_count = len(prompt.split())
    
    complex_score = sum(1 for kw in COMPLEX_KEYWORDS if kw in prompt_lower)
    simple_score = sum(1 for kw in SIMPLE_KEYWORDS if kw in prompt_lower)
    
    has_question = '?' in prompt
    has_code = any(marker in prompt for marker in ['```', 'def ', 'class ', 'function '])
    
    decision = "LOCAL"
    confidence = 0.5
    reasons = []
    
    # Rule 1: Very short prompts -> Local
    if word_count < 10:
        decision = "LOCAL"
        confidence = 0.9
        reasons.append("Very short prompt")
    
    # Rule 2: Code or complex keywords -> Cloud
    elif has_code or complex_score >= 2:
        decision = "CLOUD"
        confidence = 0.85
        reasons.append(f"Complex task detected (score: {complex_score})")
    
    # Rule 3: Long questions -> Cloud
    elif has_question and word_count > 30:
        decision = "CLOUD"
        confidence = 0.75
        reasons.append("Long question")
    
    # Rule 4: Medium length with some complexity -> Cloud
    elif word_count > 50 and complex_score >= 1:
        decision = "CLOUD"
        confidence = 0.7
        reasons.append(f"Length + complexity (words: {word_count})")
    
    # Rule 5: Simple greetings/chat -> Local
    elif simple_score >= 1 and word_count < 20:
        decision = "LOCAL"
        confidence = 0.9
        reasons.append("Simple conversational")
    
    # Default fallback
    else:
        if word_count > 40:
            decision = "CLOUD"
            confidence = 0.6
            reasons.append("Default: Medium/Long length")
        else:
            decision = "LOCAL"
            confidence = 0.6
            reasons.append("Default: Short")
    
    return {
        "decision": decision,
        "confidence": confidence,
        "word_count": word_count,
        "complex_score": complex_score,
        "reasons": reasons
    }