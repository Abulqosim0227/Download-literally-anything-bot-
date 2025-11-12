#!/bin/bash
# Script to check for sensitive data before pushing to GitHub

echo "🔍 Checking for sensitive data..."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for potential secrets (excluding config.py which is gitignored)
found_issues=0

echo "Checking for bot tokens..."
if grep -r "8335000364" --include="*.py" --exclude="config.py" . 2>/dev/null; then
    echo -e "${RED}❌ Found bot token in code!${NC}"
    found_issues=$((found_issues + 1))
else
    echo -e "${GREEN}✅ No bot tokens found${NC}"
fi

echo ""
echo "Checking for API keys..."
if grep -r "74a39ff9dccca957b9b23fab5c0878cf" --include="*.py" --exclude="config.py" . 2>/dev/null; then
    echo -e "${RED}❌ Found API key in code!${NC}"
    found_issues=$((found_issues + 1))
else
    echo -e "${GREEN}✅ No API keys found${NC}"
fi

echo ""
echo "Checking for user IDs..."
if grep -r "1907925586" --include="*.py" --exclude="config.py" . 2>/dev/null; then
    echo -e "${RED}❌ Found user ID in code!${NC}"
    found_issues=$((found_issues + 1))
else
    echo -e "${GREEN}✅ No user IDs found${NC}"
fi

echo ""
echo "Checking if config.py will be committed..."
if git ls-files | grep -q "config.py"; then
    echo -e "${RED}❌ config.py is tracked by git!${NC}"
    echo "Run: git rm --cached config.py"
    found_issues=$((found_issues + 1))
else
    echo -e "${GREEN}✅ config.py is properly ignored${NC}"
fi

echo ""
echo "Checking if bot_data.json will be committed..."
if git ls-files | grep -q "bot_data.json"; then
    echo -e "${YELLOW}⚠️  bot_data.json is tracked by git${NC}"
    echo "Run: git rm --cached bot_data.json"
    found_issues=$((found_issues + 1))
else
    echo -e "${GREEN}✅ bot_data.json is properly ignored${NC}"
fi

echo ""
echo "Checking if .log files will be committed..."
if git ls-files | grep -q "\.log$"; then
    echo -e "${YELLOW}⚠️  Log files are tracked by git${NC}"
    echo "Run: git rm --cached *.log"
    found_issues=$((found_issues + 1))
else
    echo -e "${GREEN}✅ Log files are properly ignored${NC}"
fi

echo ""
echo "═══════════════════════════════════════"
if [ $found_issues -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed! Safe to push to GitHub.${NC}"
    echo "═══════════════════════════════════════"
    exit 0
else
    echo -e "${RED}❌ Found $found_issues issue(s). Fix before pushing!${NC}"
    echo "═══════════════════════════════════════"
    exit 1
fi
