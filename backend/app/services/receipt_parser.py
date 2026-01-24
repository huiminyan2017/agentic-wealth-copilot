"""Receipt parser service using OpenAI Vision to extract spending from receipt images.

This service takes receipt images (and PDFs converted to images) and extracts structured spending data.
"""

from __future__ import annotations

import base64
import json
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import Optional, List

from openai import AzureOpenAI

from ..schemas import SpendingCreate, ReceiptParseResult
from ..settings import settings


# ---- Standard Spending Categories ----
SPENDING_CATEGORIES = [
    "Automotive",
    "Car",
    "Clothes",
    "Education",
    "Entertainment",
    "Fees & adjustments",
    "Food & drink",
    "Gas",
    "Gifts & donations",
    "Groceries",
    "Health & wellness",
    "Home fixes & update",
    "Home Furnitures",
    "Kid toy",
    "Miscellaneous",
    "Personal",
    "Tax",
    "Travel",
    "Utilities (water/gas/electric/internet/mobile)",
]

# Mapping from common AI-generated categories to our standard list
CATEGORY_MAPPING = {
    # Common variations
    "grocery": "Groceries",
    "groceries": "Groceries",
    "food": "Groceries",
    "supermarket": "Groceries",
    "restaurant": "Food & drink",
    "coffee": "Food & drink",
    "cafe": "Food & drink",
    "dining": "Food & drink",
    "fast food": "Food & drink",
    "gas": "Gas",
    "fuel": "Gas",
    "gasoline": "Gas",
    "automotive": "Automotive",
    "car": "Automotive",
    "auto": "Automotive",
    "vehicle": "Automotive",
    "electronics": "Miscellaneous",
    "clothing": "Clothes",
    "clothes": "Clothes",
    "apparel": "Clothes",
    "retail": "Miscellaneous",
    "shopping": "Miscellaneous",
    "household": "Home fixes & update",
    "home": "Home fixes & update",
    "cleaning": "Home fixes & update",
    "furniture": "Home Furnitures",
    "furnitures": "Home Furnitures",
    "toy": "Kid toy",
    "toys": "Kid toy",
    "kid": "Kid toy",
    "kids": "Kid toy",
    "children": "Kid toy",
    "pharmacy": "Health & wellness",
    "medical": "Health & wellness",
    "health": "Health & wellness",
    "wellness": "Health & wellness",
    "vitamins": "Health & wellness",
    "tax": "Tax",
    "sales tax": "Tax",
    "discount": "Fees & adjustments",
    "refund": "Fees & adjustments",
    "coupon": "Fees & adjustments",
    "savings": "Fees & adjustments",
    "fee": "Fees & adjustments",
    "service fee": "Fees & adjustments",
    "entertainment": "Entertainment",
    "education": "Education",
    "travel": "Travel",
    "hotel": "Travel",
    "flight": "Travel",
    "utilities": "Utilities (water/gas/electric/internet/mobile)",
    "bills": "Utilities (water/gas/electric/internet/mobile)",
    "electric": "Utilities (water/gas/electric/internet/mobile)",
    "electricity": "Utilities (water/gas/electric/internet/mobile)",
    "water": "Utilities (water/gas/electric/internet/mobile)",
    "internet": "Utilities (water/gas/electric/internet/mobile)",
    "phone": "Utilities (water/gas/electric/internet/mobile)",
    "mobile": "Utilities (water/gas/electric/internet/mobile)",
    "cable": "Utilities (water/gas/electric/internet/mobile)",
    "car": "Car",
    "car payment": "Car",
    "car insurance": "Car",
    "auto insurance": "Car",
    "gift": "Gifts & donations",
    "donation": "Gifts & donations",
    "personal": "Personal",
    "professional": "Miscellaneous",
    "service": "Miscellaneous",
    "miscellaneous": "Miscellaneous",
    "other": "Miscellaneous",
    "unknown": "Miscellaneous",
}


def _normalize_category(category: str) -> str:
    """Normalize a category to one of the standard categories."""
    if not category:
        return "Miscellaneous"
    
    # Check if already a standard category (case-insensitive)
    category_lower = category.lower().strip()
    for std_cat in SPENDING_CATEGORIES:
        if std_cat.lower() == category_lower:
            return std_cat
    
    # Check mapping
    if category_lower in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[category_lower]
    
    # Try partial matching
    for key, value in CATEGORY_MAPPING.items():
        if key in category_lower or category_lower in key:
            return value
    
    # Default to Miscellaneous
    return "Miscellaneous"


def _get_openai_client() -> AzureOpenAI:
    """Get the Azure OpenAI client."""
    return AzureOpenAI(
        api_key=settings.azure_openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
    )


def _convert_pdf_to_images(pdf_path: str) -> List[str]:
    """Convert PDF pages to PNG images.
    
    Returns list of paths to generated image files.
    Requires pdf2image and poppler to be installed.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        raise ImportError(
            "pdf2image is required for PDF support. "
            "Install with: pip install pdf2image\n"
            "Also requires poppler: brew install poppler (macOS) or apt-get install poppler-utils (Linux)"
        )
    
    pdf_path = Path(pdf_path)
    images = convert_from_path(str(pdf_path), dpi=200)
    
    image_paths = []
    for i, image in enumerate(images):
        # Save each page as PNG next to the PDF
        image_path = pdf_path.parent / f"{pdf_path.stem}_page{i+1}.png"
        image.save(str(image_path), "PNG")
        image_paths.append(str(image_path))
    
    return image_paths


def _convert_pdf_bytes_to_images(pdf_bytes: bytes, output_dir: Path, base_name: str) -> List[str]:
    """Convert PDF bytes to PNG images.
    
    Returns list of paths to generated image files.
    """
    try:
        from pdf2image import convert_from_bytes
    except ImportError:
        raise ImportError(
            "pdf2image is required for PDF support. "
            "Install with: pip install pdf2image\n"
            "Also requires poppler: brew install poppler (macOS) or apt-get install poppler-utils (Linux)"
        )
    
    images = convert_from_bytes(pdf_bytes, dpi=200)
    
    image_paths = []
    for i, image in enumerate(images):
        image_path = output_dir / f"{base_name}_page{i+1}.png"
        image.save(str(image_path), "PNG")
        image_paths.append(str(image_path))
    
    return image_paths


def _encode_image(image_path: str) -> str:
    """Encode image file to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _get_image_media_type(image_path: str) -> str:
    """Determine media type from file extension."""
    ext = Path(image_path).suffix.lower()
    media_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    return media_types.get(ext, "image/jpeg")


def parse_receipt_image(
    image_path: str,
    default_date: Optional[date] = None,
) -> ReceiptParseResult:
    """Parse a receipt image (or PDF) and extract spending items.
    
    Args:
        image_path: Path to the receipt image or PDF file
        default_date: Date to use if not found on receipt (defaults to today)
    
    Returns:
        ReceiptParseResult with extracted items
    """
    if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
        return ReceiptParseResult(
            items=[],
            warnings=["Azure OpenAI not configured. Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY."],
        )
    
    if default_date is None:
        default_date = date.today()
    
    # Handle PDF files by converting to images first
    if Path(image_path).suffix.lower() == ".pdf":
        try:
            image_paths = _convert_pdf_to_images(image_path)
        except ImportError as e:
            return ReceiptParseResult(
                items=[],
                warnings=[str(e)],
            )
        except Exception as e:
            return ReceiptParseResult(
                items=[],
                warnings=[f"Failed to convert PDF: {str(e)}"],
            )
        
        # Parse each page and combine results
        all_items = []
        all_warnings = []
        raw_texts = []
        
        for page_path in image_paths:
            result = _parse_single_image(page_path, default_date, image_path)
            all_items.extend(result.items)
            all_warnings.extend(result.warnings or [])
            if result.raw_text:
                raw_texts.append(result.raw_text)
        
        return ReceiptParseResult(
            items=all_items,
            raw_text="\n---PAGE BREAK---\n".join(raw_texts) if raw_texts else None,
            confidence=0.8 if all_items else 0.0,
            warnings=all_warnings,
        )
    
    # For image files, parse directly
    return _parse_single_image(image_path, default_date, image_path)


def _parse_single_image(
    image_path: str,
    default_date: date,
    original_path: str,
) -> ReceiptParseResult:
    """Parse a single image file (internal helper).
    
    Args:
        image_path: Path to the image file
        default_date: Date to use if not found on receipt
        original_path: Original file path (for receipt_path in results)
    
    Returns:
        ReceiptParseResult with extracted items
    """
    
    # Encode the image
    try:
        image_data = _encode_image(image_path)
        media_type = _get_image_media_type(image_path)
    except Exception as e:
        return ReceiptParseResult(
            items=[],
            warnings=[f"Failed to read image: {str(e)}"],
        )
    
    # Call OpenAI Vision API (standard or Azure)
    client = _get_openai_client()
    
    prompt = f"""Analyze this receipt image and extract all spending items.

IMPORTANT: Look carefully for the transaction date on the receipt. Common locations:
- Near the top (header area)
- Near the bottom (footer area)  
- Next to "Date:", "DATE", or similar labels
- In formats like: MM/DD/YYYY, MM-DD-YYYY, MMM DD YYYY, DD/MM/YYYY

For each item or line on the receipt, extract:
1. what: A category from this list ONLY: Automotive, Car, Clothes, Education, Entertainment, Fees & adjustments, Food & drink, Gas, Gifts & donations, Groceries, Health & wellness, Home fixes & update, Home Furnitures, Kid toy, Miscellaneous, Personal, Tax, Travel, Utilities (water/gas/electric/internet/mobile)
2. amount: The dollar amount. Use NEGATIVE numbers for discounts/coupons (e.g., amounts ending with "-" like "4.00-" = -4.00)
3. description: Brief description of the specific item(s)

CATEGORY GUIDANCE:
- Food at grocery stores (Costco, Walmart, etc.) → "Groceries"
- Food at restaurants/cafes → "Food & drink"
- Fuel/gasoline → "Gas"
- Household repairs, tools, cleaning supplies → "Home fixes & update"
- Furniture, decor, home furnishings → "Home Furnitures"
- Toys, games for children → "Kid toy"
- Clothing, apparel, shoes → "Clothes"
- Electronics, general merchandise → "Miscellaneous"
- Medical, pharmacy, vitamins → "Health & wellness"
- Tax lines → "Tax"
- If uncertain, use "Miscellaneous"

DISCOUNT HANDLING:
- Lines with amounts ending in "-" (like "4.00-" or "9.00-") are DISCOUNTS - extract as negative: -4.00, -9.00
- Lines starting with "/" reference the previous item (e.g., "/4165671", "/9022010") - these are discounts, use negative amount
- Instant savings, coupons, member discounts should all be NEGATIVE amounts
- IMPORTANT: Extract EVERY discount line separately, even if multiple discounts appear on the receipt

Also extract:
- The store/merchant name
- The transaction date (MUST be in format: YYYY-MM-DD)
- The receipt total (the final amount charged, including tax)
- The tax amount (if shown separately)

If you cannot find the date on the receipt, use this default: {default_date.isoformat()}

Return JSON in this exact format:
{{
    "date": "YYYY-MM-DD",
    "items": [
        {{"what": "Groceries", "amount": 19.99, "description": "KLNX LOTION"}},
        {{"what": "Fees & adjustments", "amount": -4.00, "description": "Instant savings on KLNX LOTION"}}
    ],
    "merchant": "Store Name",
    "receipt_total": 15.99,
    "tax_amount": 1.20
}}

IMPORTANT:
- Include ALL line items (individual products/items), tax lines, but NOT subtotals or totals
- DISCOUNTS must be NEGATIVE amounts
- The sum of all item amounts (including negative discounts) + tax should equal receipt_total
- Be accurate with amounts. Return only valid JSON."""

    try:
        response = client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{image_data}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=1000,
        )
        
        raw_text = response.choices[0].message.content or ""
        
        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to find raw JSON
            json_str = raw_text.strip()
        
        # Parse the JSON
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            return ReceiptParseResult(
                items=[],
                raw_text=raw_text,
                warnings=[f"Failed to parse JSON response: {str(e)}"],
            )
        
        # Extract date with multiple format support
        receipt_date = default_date
        if "date" in data and data["date"]:
            date_str = str(data["date"]).strip()
            # Try ISO format first (YYYY-MM-DD)
            try:
                receipt_date = date.fromisoformat(date_str)
            except (ValueError, TypeError):
                # Try common US formats
                from datetime import datetime
                for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y", 
                           "%B %d, %Y", "%b %d, %Y", "%d/%m/%Y", "%Y/%m/%d"]:
                    try:
                        receipt_date = datetime.strptime(date_str, fmt).date()
                        break
                    except ValueError:
                        continue
        
        # Extract merchant
        merchant = data.get("merchant")
        
        # Track if we found a real date (different from default)
        found_real_date = receipt_date != default_date
        
        # Debug: track what date was extracted
        date_info = f"Extracted date: {receipt_date.isoformat()} (from receipt: '{data.get('date', 'not found')}')"
        
        # Words that indicate this is a total/subtotal line, not an actual item
        # Note: 'tax' handled separately below - we capture it as a "Tax" category item
        total_keywords = {'total', 'subtotal', 'sub-total', 'grand total', 'balance', 'change', 'payment', 'cash', 'credit', 'debit', 'visa', 'mastercard', 'amex'}
        tax_keywords = {'tax', 'sales tax', 'state tax', 'local tax', 'vat'}
        
        # Convert to SpendingCreate items, filtering out totals
        items = []
        for item in data.get("items", []):
            try:
                description = item.get("description", "") or ""
                what = item.get("what", "Unknown") or ""
                
                # Skip items that look like totals (but not tax)
                desc_lower = description.lower()
                what_lower = what.lower()
                if any(kw in desc_lower or kw in what_lower for kw in total_keywords):
                    continue
                
                # Skip if description contains "total" phrases
                if "total purchase" in desc_lower or "total groceries" in desc_lower:
                    continue
                
                # Get the amount (can be negative for discounts)
                item_amount = float(item.get("amount", 0))
                
                # Handle tax items specially - add as "Tax" category with heuristic description
                if any(kw in desc_lower or kw in what_lower for kw in tax_keywords):
                    # Create descriptive tax identifier: merchant-date-tax
                    merchant_slug = (merchant or "unknown").lower().replace(" ", "-")[:20]
                    tax_desc = f"{merchant_slug}-{receipt_date.isoformat()}-tax"
                    items.append(SpendingCreate(
                        date=receipt_date,
                        what="Tax",
                        amount=item_amount,
                        quantity=1,
                        merchant=merchant,
                        description=tax_desc,
                        source="receipt",
                        receipt_path=original_path,
                    ))
                    continue
                
                # Handle discounts (negative amounts) - merge into previous item
                # Detect discount patterns: negative amount, discount keywords, or item reference codes
                is_discount = (
                    item_amount < 0 or 
                    'discount' in what_lower or 
                    'saving' in desc_lower or 
                    'coupon' in desc_lower or
                    'instant' in desc_lower or
                    desc_lower.startswith('/') or  # Reference to previous item like "/4165671"
                    re.match(r'^/?\d{5,}', description.strip()) or  # Item code reference like "/9022010" or "9022010"
                    'fees & adjustments' in what_lower  # AI categorized as adjustment
                )
                
                if is_discount and items:
                    # Merge discount into the previous item
                    prev_item = items[-1]
                    discount_amount = abs(item_amount) if item_amount < 0 else item_amount
                    new_amount = prev_item.amount - discount_amount
                    
                    # Update description to note discount was applied
                    discount_note = f" (${discount_amount:.2f} off)"
                    new_desc = (prev_item.description or prev_item.what) + discount_note
                    
                    # Replace previous item with discounted version
                    items[-1] = SpendingCreate(
                        date=prev_item.date,
                        what=prev_item.what,
                        amount=new_amount,
                        quantity=prev_item.quantity,
                        merchant=prev_item.merchant,
                        description=new_desc,
                        source=prev_item.source,
                        receipt_path=prev_item.receipt_path,
                    )
                    continue
                elif is_discount and not items:
                    # Discount without previous item - keep as separate item under Fees & adjustments
                    items.append(SpendingCreate(
                        date=receipt_date,
                        what="Fees & adjustments",
                        amount=item_amount,
                        quantity=1,
                        merchant=merchant,
                        description=description if description else "Discount/Savings",
                        source="receipt",
                        receipt_path=original_path,
                    ))
                    continue
                    
                # Normalize category to standard list
                normalized_what = _normalize_category(what)
                
                items.append(SpendingCreate(
                    date=receipt_date,
                    what=normalized_what,
                    amount=item_amount,
                    quantity=int(item.get("quantity", 1)),
                    merchant=merchant,
                    description=description if description else None,
                    source="receipt",
                    receipt_path=original_path,
                ))
            except (ValueError, TypeError) as e:
                continue
        
        # Validate: sum of items should match receipt total
        warnings_list = [date_info] if items else []
        receipt_total = data.get("receipt_total")
        if receipt_total is not None and items:
            try:
                receipt_total = float(receipt_total)
                items_sum = sum(item.amount for item in items)
                difference = abs(items_sum - receipt_total)
                
                # Allow small tolerance for rounding (e.g., $0.05)
                if difference > 0.05:
                    warnings_list.append(
                        f"⚠️ Total mismatch: items sum to ${items_sum:.2f}, "
                        f"but receipt shows ${receipt_total:.2f} (diff: ${difference:.2f}). "
                        f"Some items may be missing or amounts incorrect."
                    )
                    # Lower confidence when totals don't match
                    confidence = 0.5
                else:
                    confidence = 0.9  # Higher confidence when totals match
            except (ValueError, TypeError):
                confidence = 0.8
        else:
            confidence = 0.8 if items else 0.0
        
        return ReceiptParseResult(
            items=items,
            extracted_date=receipt_date if found_real_date else None,  # Only set if we found a real date
            raw_text=raw_text,
            confidence=confidence,
            warnings=warnings_list,
        )
        
    except Exception as e:
        return ReceiptParseResult(
            items=[],
            warnings=[f"OpenAI API error: {str(e)}"],
        )


def parse_receipt_from_bytes(
    file_bytes: bytes,
    filename: str,
    person: str,
    default_date: Optional[date] = None,
) -> ReceiptParseResult:
    """Parse a receipt from uploaded bytes (image or PDF).
    
    Saves the file to disk first, then parses it.
    For PDFs, converts to images before parsing.
    
    Args:
        file_bytes: Raw file bytes (image or PDF)
        filename: Original filename
        person: Person name for storage path
        default_date: Date to use if not found on receipt
    
    Returns:
        ReceiptParseResult with extracted items
    """
    import uuid
    
    from .storage import ORIGINAL_DATA_DIR
    
    # Save the file
    receipt_dir = ORIGINAL_DATA_DIR / person / "receipts"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    ext = Path(filename).suffix.lower() or ".jpg"
    unique_name = str(uuid.uuid4())
    saved_path = receipt_dir / f"{unique_name}{ext}"
    
    with open(saved_path, "wb") as f:
        f.write(file_bytes)
    
    # Handle PDF files
    if ext == ".pdf":
        try:
            image_paths = _convert_pdf_bytes_to_images(file_bytes, receipt_dir, unique_name)
        except ImportError as e:
            return ReceiptParseResult(
                items=[],
                warnings=[str(e)],
            )
        except Exception as e:
            return ReceiptParseResult(
                items=[],
                warnings=[f"Failed to convert PDF: {str(e)}"],
            )
        
        # Parse each page and combine results
        all_items = []
        all_warnings = []
        raw_texts = []
        found_receipt_date = None  # Track actual receipt date found (not default)
        found_receipt_total = None  # Track receipt total for validation
        
        effective_default = default_date or date.today()
        
        for page_path in image_paths:
            result = _parse_single_image(page_path, effective_default, str(saved_path))
            all_items.extend(result.items)
            
            # Check if this page found a real date (use extracted_date field)
            # This works even if all items on that page were filtered out (e.g., only "Total")
            if result.extracted_date and found_receipt_date is None:
                found_receipt_date = result.extracted_date
            
            # Extract receipt_total from raw_text (JSON response)
            if result.raw_text and found_receipt_total is None:
                import re
                total_match = re.search(r'"receipt_total"\s*:\s*([\d.]+)', result.raw_text)
                if total_match:
                    try:
                        found_receipt_total = float(total_match.group(1))
                    except ValueError:
                        pass
            
            all_warnings.extend(result.warnings or [])
            if result.raw_text:
                raw_texts.append(result.raw_text)
        
        # If we found a real receipt date on any page, apply it to ALL items
        if found_receipt_date:
            for item in all_items:
                item.date = found_receipt_date
            # Single consolidated date message
            final_warnings = [f"Extracted date: {found_receipt_date.isoformat()} (from receipt)"]
        else:
            # No date found on any page, all items use default
            final_warnings = [f"Extracted date: {effective_default.isoformat()} (used default - no date found on receipt)"]
        
        # Validate combined total across all pages
        if found_receipt_total is not None and all_items:
            items_sum = sum(item.amount for item in all_items)
            difference = abs(items_sum - found_receipt_total)
            
            if difference > 0.05:
                final_warnings.append(
                    f"⚠️ Total mismatch: items sum to ${items_sum:.2f}, "
                    f"but receipt shows ${found_receipt_total:.2f} (diff: ${difference:.2f}). "
                    f"Some items may be missing or amounts incorrect."
                )
                confidence = 0.5
            else:
                final_warnings.append(f"✓ Total verified: ${items_sum:.2f} matches receipt")
                confidence = 0.9
        else:
            confidence = 0.8 if all_items else 0.0
        
        return ReceiptParseResult(
            items=all_items,
            extracted_date=found_receipt_date,
            raw_text="\n---PAGE BREAK---\n".join(raw_texts) if raw_texts else None,
            confidence=confidence,
            warnings=final_warnings,
        )
    
    # Parse the saved image
    result = parse_receipt_image(str(saved_path), default_date)
    
    # Update receipt_path in items to use the saved path
    for item in result.items:
        item.receipt_path = str(saved_path)
    
    return result
