"""
autocomplete_engine.py
======================
Universal Smart Autocomplete Engine for SmartBuy:
- Supports ALL product categories (Electronics, Home Appliances, Kitchen, Groceries,
  Personal Care, Beauty, Fashion, Baby, Pet, Stationery, Sports, Furniture, Automotive, Books)
- Multi-tier matching: Prefix Matching, Token Matching, RapidFuzz Fuzzy Search, Typo Correction
- SQLite search history integration for organic learning
- Returns 10–15 intelligent suggestions per query
"""

import re
import logging
from rapidfuzz import fuzz
from database import get_recent_queries, get_trending_queries

logger = logging.getLogger("smartbuy.autocomplete")

# ═══════════════════════════════════════════════════════════════════════════
# UNIVERSAL MULTI-CATEGORY PRODUCT DICTIONARY
# Spans all 14+ e-commerce & grocery categories
# ═══════════════════════════════════════════════════════════════════════════
UNIVERSAL_PRODUCT_DICTIONARY = [
    # ── Electronics ────────────────────────────────────────────────────────
    "Smartphone", "Smartphones", "Mi Smartphone", "Samsung Galaxy Smartphone", "Apple iPhone 15",
    "Apple iPhone 14", "Apple iPhone 13", "OnePlus Smartphone", "Realme Mobile Phone", "Vivo Smartphone",
    "Oppo Mobile Phone", "Google Pixel Phone", "Gaming Phone", "Laptop", "Laptops", "Gaming Laptop",
    "Dell Laptop", "HP Laptop", "Lenovo IdeaPad Laptop", "Asus ROG Laptop", "Apple MacBook Air",
    "Apple MacBook Pro", "Tablet", "Tablets", "Apple iPad", "Samsung Galaxy Tab", "Lenovo Tab",
    "Smartwatch", "Smart Watches", "boAt Smartwatch", "Noise Smartwatch", "Apple Watch",
    "Samsung Galaxy Watch", "Fire-Boltt Smartwatch", "Earbuds", "Wireless Earbuds", "boAt Airdopes",
    "Realme Buds", "OnePlus Earbuds", "Apple AirPods", "Headphones", "Bluetooth Headphones",
    "Sony Headphones", "JBL Headphones", "Noise Cancelling Headphones", "Camera", "Cameras",
    "DSLR Camera", "Canon Camera", "Nikon Camera", "Sony Alpha Camera", "Action Camera",
    "GoPro Camera", "Television", "Televisions", "Smart TV", "LED TV", "OLED TV", "4K TV",
    "Sony Bravia TV", "Samsung Smart TV", "LG Smart TV", "Xiaomi TV", "Monitor", "Monitors",
    "Gaming Monitor", "LG Monitor", "Dell Monitor", "Printer", "Printers", "HP Printer",
    "Canon Printer", "Epson InkTank Printer", "Keyboard", "Keyboards", "Wireless Keyboard",
    "Mechanical Keyboard", "Logitech Keyboard", "Mouse", "Wireless Mouse", "Gaming Mouse",
    "Logitech Mouse", "Router", "WiFi Router", "TP-Link Router", "Power Bank", "Power Banks",
    "Mi Power Bank", "Anker Power Bank", "Speaker", "Speakers", "Bluetooth Speaker",
    "JBL Bluetooth Speaker", "Soundbar", "Home Theatre System",

    # ── Home Appliances ───────────────────────────────────────────────────
    "Refrigerator", "Refrigerators", "Single Door Refrigerator", "Double Door Refrigerator",
    "Samsung Refrigerator", "LG Refrigerator", "Whirlpool Refrigerator", "Washing Machine",
    "Washing Machines", "Front Load Washing Machine", "Top Load Washing Machine", "LG Washing Machine",
    "Samsung Washing Machine", "Air Conditioner", "Air Conditioners", "Split AC", "Inverter AC",
    "Voltas AC", "Daikin AC", "Lloyd AC", "Air Cooler", "Air Coolers", "Symphony Air Cooler",
    "Microwave Oven", "Microwave Ovens", "Convection Microwave", "IFB Microwave", "LG Microwave",
    "Induction Stove", "Induction Cooktop", "Prestige Induction Stove", "Philips Induction Stove",
    "Mixer Grinder", "Mixer Grinders", "Prestige Mixer Grinder", "Juicer Mixer Grinder",
    "Water Purifier", "Water Purifiers", "RO Water Purifier", "Kent Water Purifier", "Eureka Forbes Water Purifier",
    "Vacuum Cleaner", "Robot Vacuum Cleaner", "Dyson Vacuum Cleaner", "Geyser", "Water Heater",
    "Bajaj Geyser", "Crompton Geyser", "Ceiling Fan", "Ceiling Fans", "BLDC Fan", "Crompton Fan",
    "Iron Box", "Steam Iron", "Dry Iron", "Philips Steam Iron", "Room Heater", "Dishwasher",

    # ── Kitchen Products ──────────────────────────────────────────────────
    "Pressure Cooker", "Pressure Cookers", "Hawkins Pressure Cooker", "Prestige Pressure Cooker",
    "Frying Pan", "Non-Stick Frying Pan", "Cookware Set", "Non-Stick Cookware Set", "Knife Set",
    "Kitchen Knife Set", "Water Bottle", "Water Bottles", "Stainless Steel Water Bottle", "Milton Water Bottle",
    "Lunch Box", "Insulated Lunch Box", "Gas Stove", "2 Burner Gas Stove", "3 Burner Gas Stove",
    "Mixer Jar", "Storage Containers", "Kitchen Storage Containers", "Plastic Containers",
    "Plates", "Dinner Set", "Bowls", "Soup Bowls", "Spoons", "Cutlery Set", "Chimney", "Kitchen Chimney",
    "Gas Lighter", "Chopping Board", "Hot Pot", "Thermos Flask",

    # ── Groceries ─────────────────────────────────────────────────────────
    "Rice", "Basmati Rice", "Fortune Basmati Rice", "India Gate Basmati Rice", "Wheat Flour",
    "Aashirvaad Atta", "Whole Wheat Atta", "Sugar", "White Sugar", "Jaggery", "Salt", "Iodized Salt",
    "Tata Salt", "Cooking Oil", "Sunflower Oil", "Mustard Oil", "Fortune Sunflower Oil",
    "Ghee", "Amul Ghee", "Cow Ghee", "Milk", "Amul Milk", "Toned Milk", "Full Cream Milk",
    "Curd", "Amul Curd", "Yogurt", "Butter", "Amul Butter", "Cheese", "Cheese Slices", "Mozzarella Cheese",
    "Eggs", "Farm Eggs", "Bread", "Brown Bread", "White Bread", "Biscuits", "Parle-G Biscuits",
    "Oreo Biscuits", "Good Day Biscuits", "Chocolates", "Cadbury Dairy Milk", "KitKat Chocolate",
    "Ferrero Rocher", "Tea", "Tata Tea", "Red Label Tea", "Green Tea", "Coffee", "Nescafe Coffee",
    "Bru Instant Coffee", "Spices", "Turmeric Powder", "Chilli Powder", "Garam Masala", "Dal",
    "Toor Dal", "Moong Dal", "Chana Dal", "Noodles", "Maggi Noodles", "Yippee Noodles", "Snacks",
    "Potato Chips", "Kurkure", "Namkeen", "Juices", "Real Fruit Juice", "Tropicana Juice",
    "Soft Drinks", "Soft Drink", "Coca Cola", "Pepsi", "Thums Up", "Sprite", "Mineral Water", "Bisleri Water",
    "Soya Chunks", "Fortune Soya Chunks", "Oats", "Quaker Oats", "Honey", "Dabur Honey", "Jam", "Kissan Jam",

    # ── Personal Care ─────────────────────────────────────────────────────
    "Soap", "Soaps", "Dove Soap", "Dettol Soap", "Lux Soap", "Pears Soap", "Face Wash",
    "Himalaya Purifying Neem Face Wash", "Garnier Face Wash", "Mamaearth Face Wash", "Clean & Clear Face Wash",
    "Shampoo", "Shampoos", "Head & Shoulders Shampoo", "Dove Shampoo", "Clinic Plus Shampoo",
    "Tresemme Shampoo", "Conditioner", "Hair Conditioner", "Toothpaste", "Colgate Toothpaste",
    "Sensodyne Toothpaste", "Pepsodent Toothpaste", "Toothbrush", "Electric Toothbrush",
    "Face Cream", "Fair & Lovely Cream", "Nivea Cream", "Olay Face Cream", "Body Lotion",
    "Nivea Body Lotion", "Vaseline Body Lotion", "Hair Oil", "Parachute Coconut Oil",
    "Bajaj Almond Hair Oil", "Deodorant", "Fogg Deodorant", "Nivea Deodorant", "Wild Stone Spray",
    "Perfume", "Perfumes", "Men Perfume", "Women Perfume", "Fogg Perfume", "Sunscreen",
    "Sunscreen Lotion", "Neutrogena Sunscreen", "Lotus Sunscreen", "Moisturizer", "Face Moisturizer",
    "Lip Balm", "Nivea Lip Balm", "Maybelline Lip Balm", "Hand Wash", "Dettol Hand Wash",
    "Body Wash", "Shower Gel", "Shaving Cream", "Gillette Shaving Foam", "Razors",

    # ── Beauty Products ───────────────────────────────────────────────────
    "Lipstick", "Lipsticks", "Matte Lipstick", "Maybelline Lipstick", "Lakme Lipstick",
    "Foundation", "Liquid Foundation", "Maybelline Fit Me Foundation", "Compact Powder",
    "Lakme Compact Powder", "Kajal", "Lakme Eyeconic Kajal", "Eyeliner", "Liquid Eyeliner",
    "Mascara", "Waterproof Mascara", "Nail Polish", "Nail Enamel", "Face Serum",
    "Vitamin C Face Serum", "Ordinary Serum", "Face Mask", "Sheet Mask", "Makeup Kit",
    "Complete Makeup Kit", "Hair Dryer", "Philips Hair Dryer", "Nova Hair Dryer",
    "Hair Straightener", "Philips Hair Straightener", "Cleansing Milk", "Hair Color", "Garnier Hair Color",

    # ── Fashion ───────────────────────────────────────────────────────────
    "Shirt", "Shirts", "Men Casual Shirt", "Men Formal Shirt", "Cotton Shirt", "T-Shirt",
    "T-Shirts", "Men T-Shirt", "Women T-Shirt", "Oversized T-Shirt", "Polo T-Shirt", "Jeans",
    "Men Jeans", "Women Jeans", "Denim Jeans", "Levis Jeans", "Dress", "Dresses", "Women Dress",
    "Party Dress", "Saree", "Sarees", "Cotton Saree", "Silk Saree", "Banarasi Saree", "Shoes",
    "Running Shoes", "Casual Shoes", "Formal Shoes", "Sneakers", "Nike Shoes", "Adidas Shoes",
    "Puma Shoes", "Sandals", "Men Sandals", "Women Sandals", "Heels", "Watch", "Watches",
    "Men Watch", "Women Watch", "Casio Watch", "Titan Watch", "Fastrack Watch", "Handbag",
    "Handbags", "Women Handbag", "Wallet", "Wallets", "Men Leather Wallet", "Sunglasses",
    "Ray-Ban Sunglasses", "Aviator Sunglasses", "Belt", "Belts", "Men Leather Belt", "Socks",
    "Cotton Socks", "Boots", "Jacket", "Denim Jacket", "Winter Jacket", "Kurti", "Women Kurti",
    "Trousers", "Hoodies", "Men Hoodie",

    # ── Baby Products ─────────────────────────────────────────────────────
    "Baby Diapers", "Pampers Baby Diapers", "MamyPoko Pants", "Huggies Diapers", "Baby Soap",
    "Himalaya Baby Soap", "Johnson Baby Soap", "Baby Shampoo", "Johnson Baby Shampoo",
    "Baby Powder", "Johnson Baby Powder", "Baby Lotion", "Baby Food", "Cerelac Baby Food",
    "Baby Wipes", "Himalaya Baby Wipes", "Baby Stroller", "Baby Carrier",

    # ── Pet Products ──────────────────────────────────────────────────────
    "Dog Food", "Pedigree Dog Food", "Royal Canin Dog Food", "Cat Food", "Whiskas Cat Food",
    "Pet Shampoo", "Dog Shampoo", "Pet Toys", "Dog Toys", "Pet Accessories", "Dog Collar", "Cat Litter",

    # ── Stationery ────────────────────────────────────────────────────────
    "Notebook", "Notebooks", "Classmate Notebook", "Spiral Notebook", "Pen", "Pens",
    "Ball Pen", "Gel Pen", "Reynolds Pen", "Parker Pen", "Pencil", "Pencils", "Apsara Pencil",
    "Camel Pencil", "Marker", "Whiteboard Marker", "Permanent Marker", "Calculator",
    "Casio Scientific Calculator", "School Bag", "College Backpack", "Glue", "Fevicol", "Scissors",
    "Sticky Notes", "File Folder",

    # ── Sports & Fitness ──────────────────────────────────────────────────
    "Cricket Bat", "MRF Cricket Bat", "SS Cricket Bat", "Football", "Nike Football",
    "Adidas Football", "Yoga Mat", "Anti-Slip Yoga Mat", "Dumbbells", "Rubber Dumbbells",
    "Adjustable Dumbbells", "Treadmill", "Folding Treadmill", "Protein Powder",
    "Optimum Nutrition Whey Protein", "MuscleBlaze Whey Protein", "Badminton Racket",
    "Yonex Badminton Racket", "Resistance Bands", "Exercise Bike",

    # ── Furniture ─────────────────────────────────────────────────────────
    "Chair", "Chairs", "Office Chair", "Ergonomic Office Chair", "Plastic Chair", "Table",
    "Tables", "Study Table", "Dining Table", "Computer Table", "Sofa", "Sofas", "3 Seater Sofa",
    "Sofa Bed", "Bed", "Beds", "King Size Bed", "Queen Size Bed", "Wooden Bed", "Wardrobe",
    "3 Door Wardrobe", "Metal Wardrobe", "Bookshelf", "Recliner", "Recliner Chair",

    # ── Automotive ────────────────────────────────────────────────────────
    "Engine Oil", "Castrol Engine Oil", "Motul Engine Oil", "Helmet", "Studds Helmet",
    "Vega Helmet", "Car Cover", "Waterproof Car Cover", "Bike Cover", "Car Shampoo",
    "Car Polish", "Microfiber Cloth", "Car Phone Mount", "Mobile Holder for Car",

    # ── Books ─────────────────────────────────────────────────────────────
    "Academic Books", "NCERT Books", "Story Books", "Novels", "English Novels",
    "Competitive Exam Books", "NEET Books", "JEE Main Books", "UPSC Books", "Fiction Books",
    "Self-Help Books", "Comic Books", "Atomic Habits Book",
]


class TrieNode:
    def __init__(self):
        self.children = {}
        self.is_end_of_word = False
        self.products = set()


class ProductTrie:
    """Trie structure optimized for ultra-fast multi-word prefix & token autocomplete."""

    def __init__(self):
        self.root = TrieNode()

    def insert(self, product_name: str) -> None:
        """Insert a product name by full title and by word tokens."""
        if not product_name:
            return
        name_clean = product_name.strip()
        if len(name_clean) < 2:
            return

        name_lower = name_clean.lower()
        tokens = re.split(r'\s+', name_lower)

        # Insert full term
        self._insert_string(name_lower, name_clean)

        # Insert each word token for token-level prefix matching
        for token in tokens:
            if len(token) >= 2:
                self._insert_string(token, name_clean)

    def _insert_string(self, key: str, original_name: str) -> None:
        node = self.root
        for char in key:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
            node.products.add(original_name)
        node.is_end_of_word = True

    def search_prefix(self, prefix: str, limit: int = 15) -> list:
        """Find matching terms in Trie for a given prefix."""
        prefix_clean = prefix.strip().lower()
        if not prefix_clean:
            return []

        node = self.root
        for char in prefix_clean:
            if char not in node.children:
                return []
            node = node.children[char]

        matches = list(node.products)
        # Prioritize exact prefix start, then length, then alphabetical
        matches.sort(key=lambda s: (
            not s.lower().startswith(prefix_clean),
            len(s),
            s
        ))
        return matches[:limit]


# Global Trie Instance
_trie_instance = None


def build_trie_from_history() -> ProductTrie:
    """Build or return Master Trie populated with Universal Dictionary + search history."""
    return get_master_trie()


def get_master_trie() -> ProductTrie:
    """Return singleton Master Trie built from Universal Product Dictionary + SQLite search history."""
    global _trie_instance
    if _trie_instance is None:
        trie = ProductTrie()

        # 1. Populate from Universal Product Dictionary
        for term in UNIVERSAL_PRODUCT_DICTIONARY:
            trie.insert(term)

        # 2. Populate from SQLite Search History (dynamic organic growth)
        try:
            recent = get_recent_queries(limit=1000)
            for q in recent:
                if q:
                    trie.insert(q)
        except Exception as e:
            logger.warning(f"Could not load search history into Trie: {e}")

        _trie_instance = trie

    return _trie_instance


def fuzzy_search_terms(query: str, candidates: list, limit: int = 10) -> list:
    """
    Perform intelligent fuzzy matching using RapidFuzz for typo correction.
    """
    query_clean = query.strip().lower()
    if not query_clean or len(query_clean) < 2:
        return []

    scored = []
    seen = set()

    for item in candidates:
        item_lower = item.lower()
        if item_lower in seen:
            continue

        # RapidFuzz partial and token_set ratio
        score_set = fuzz.token_set_ratio(query_clean, item_lower)
        score_part = fuzz.partial_ratio(query_clean, item_lower)
        best_score = max(score_set, score_part)

        if best_score >= 60:
            scored.append((best_score, len(item), item))
            seen.add(item_lower)

    scored.sort(key=lambda x: (-x[0], x[1], x[2]))
    return [item for _, _, item in scored[:limit]]


def get_autocomplete_suggestions(trie: ProductTrie = None, query: str = "", limit: int = 12) -> list:
    """
    Get intelligent, multi-category search suggestions.

    Args:
        trie: Optional ProductTrie (defaults to Master Trie)
        query: User input keyword
        limit: Max suggestions to return (10–15)

    Returns:
        list of string suggestions
    """
    q_clean = query.strip().lower()

    # Default fallback on empty query
    if not q_clean or len(q_clean) < 2:
        try:
            trending = get_trending_queries(limit=limit)
            if trending:
                return trending
        except Exception:
            pass
        return UNIVERSAL_PRODUCT_DICTIONARY[:limit]

    if trie is None:
        trie = get_master_trie()

    results = []
    seen = set()

    def add_item(item_text):
        norm = item_text.strip()
        norm_key = norm.lower()
        if norm_key and norm_key not in seen:
            seen.add(norm_key)
            results.append(norm)

    # 1. Direct Trie Prefix & Token Matching (O(k))
    trie_matches = trie.search_prefix(q_clean, limit=limit * 2)
    for item in trie_matches:
        add_item(item)

    # 2. Additional Dictionary Token Matching
    if len(results) < limit:
        for term in UNIVERSAL_PRODUCT_DICTIONARY:
            t_lower = term.lower()
            if t_lower not in seen:
                # Check if any word token in term starts with q_clean
                tokens = t_lower.split()
                if any(tok.startswith(q_clean) for tok in tokens):
                    add_item(term)
                    if len(results) >= limit:
                        break

    # 3. RapidFuzz Fuzzy Fallback (for typos like 'facewsh', 'sop', 'smartwth')
    if len(results) < limit:
        fuzzy_matches = fuzzy_search_terms(q_clean, UNIVERSAL_PRODUCT_DICTIONARY, limit=limit)
        for item in fuzzy_matches:
            add_item(item)

    # 4. Search History Fallback
    if len(results) < limit:
        try:
            history = get_recent_queries(limit=300)
            fuzzy_hist = fuzzy_search_terms(q_clean, history, limit=limit)
            for item in fuzzy_hist:
                add_item(item)
        except Exception:
            pass

    return results[:limit]

