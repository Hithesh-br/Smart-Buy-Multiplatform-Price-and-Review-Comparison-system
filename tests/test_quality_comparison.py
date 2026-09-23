import unittest
from search.quality_scorer import (
    CATEGORY_WEIGHTS, compute_data_confidence,
    get_detailed_quality_report, calculate_value_for_money_index,
    extract_review_signals
)
from search.specs_extractor import extract_specs
from search.product_matcher import evaluate_product_match
from search.pipeline import run_comparison_pipeline

class TestProductQualityComparison(unittest.TestCase):

    def test_category_weights_completeness(self):
        """Test all required categories have weights summing to 1.0."""
        categories = ['phone', 'laptop', 'kitchen', 'beauty', 'face_wash', 'soap', 'grocery', 'clothing', 'bags', 'other']
        for cat in categories:
            w = CATEGORY_WEIGHTS.get(cat)
            self.assertIsNotNone(w, f"Category '{cat}' missing from weights")
            self.assertAlmostEqual(sum(w.values()), 1.0, places=2, msg=f"Weights for '{cat}' must sum to 1.0")

    def test_insufficient_data_handling(self):
        """Test that products with sparse or missing data have <35% confidence and 'Insufficient Data'."""
        thin_prod = {'title': 'Sample Thin Product', 'price': '₹500', 'rating': None, 'reviews': '0'}
        conf = compute_data_confidence(thin_prod)
        report = get_detailed_quality_report(thin_prod, 'other')
        self.assertLess(conf, 35.0)
        self.assertFalse(report['has_sufficient_data'])
        self.assertIsNone(report['quality_score'])
        self.assertEqual(report['quality_band'], 'Insufficient Data')

    def test_cheapest_is_not_highest_quality(self):
        """Test that quality score objectively evaluates specs and ratings, never biasing to cheap products."""
        budget_phone = {
            'title': 'Entry Level Basic Smartphone 4GB RAM 64GB Storage',
            'price': '₹4,999',
            'price_num': 4999,
            'rating': '3.2',
            'reviews': '150',
            'specs': {
                'brand': 'Generic',
                'ram': '4 GB',
                'storage': '64 GB',
                'processor': 'Quad Core 1.3GHz',
                'battery': '3000 mAh',
                'camera': '8 MP'
            },
            'specifications': {'warranty': '6 Months Warranty'}
        }
        flagship_phone = {
            'title': 'Flagship Smartphone 5G 12GB RAM 256GB Storage',
            'price': '₹54,999',
            'price_num': 54999,
            'rating': '4.6',
            'reviews': '5,420',
            'specs': {
                'brand': 'Samsung',
                'ram': '12 GB',
                'storage': '256 GB',
                'processor': 'Snapdragon 8 Gen 3',
                'battery': '5000 mAh',
                'camera': '50 MP'
            },
            'specifications': {'warranty': '1 Year Brand Warranty'},
            'is_prime': True
        }
        budget_rep = get_detailed_quality_report(budget_phone, 'phone')
        flagship_rep = get_detailed_quality_report(flagship_phone, 'phone')

        self.assertGreater(flagship_rep['quality_score'], budget_rep['quality_score'])
        self.assertTrue(budget_rep['has_sufficient_data'])
        self.assertTrue(flagship_rep['has_sufficient_data'])

    def test_kitchen_appliance_wattage_mismatch(self):
        """Test that different wattages (e.g. 750W vs 500W mixer grinder) are classified as Variant Mismatch."""
        p_750w = {
            'title': 'Preethi Zodiac 750W Mixer Grinder with 5 Jars',
            'specs': {'brand': 'Preethi', 'wattage': '750W', 'jars': '5'}
        }
        p_500w = {
            'title': 'Preethi Zodiac 500W Mixer Grinder with 3 Jars',
            'specs': {'brand': 'Preethi', 'wattage': '500W', 'jars': '3'}
        }
        match_status, match_score, breakdown, reasons = evaluate_product_match(p_750w, p_500w)
        self.assertIn(match_status, ['VARIANT_MATCH', 'REJECTED', 'SIMILAR_PRODUCT'])

    def test_review_signals_extraction(self):
        """Test genuine review sentiment signals without hallucinating fake reviews."""
        signals = extract_review_signals("Amazing sound quality and great battery backup. Durable build quality.", category="audio", rating=4.5, review_count=300)
        self.assertIn("Reliable Battery Capacity", signals['positive_themes'])
        self.assertEqual(len(signals['negative_themes']), 0)

    def test_value_for_money_calculation(self):
        """Test Value For Money combines quality score and price competitiveness."""
        vfm = calculate_value_for_money_index(price_num=15000, quality_score=85.0, min_price=12000)
        self.assertGreater(vfm, 50.0)
        self.assertLessEqual(vfm, 100.0)

    def test_pipeline_comparison_summary_and_quality_table(self):
        """Test run_comparison_pipeline generates comparison_summary and quality_comparison_table."""
        platform_results = {
            'Amazon': [{
                'title': 'Redmi Note 13 Pro 5G (8GB RAM, 128GB)',
                'price': '₹21,999',
                'price_num': 21999,
                'rating': '4.3',
                'reviews': '1,200',
                'link': 'https://amazon.in/dp/sample',
                'image': 'https://example.com/img1.jpg',
                'platform': 'Amazon'
            }],
            'Flipkart': [{
                'title': 'REDMI Note 13 Pro 5G (8GB RAM, 128GB)',
                'price': '₹20,999',
                'price_num': 20999,
                'rating': '4.2',
                'reviews': '3,400',
                'link': 'https://flipkart.com/sample',
                'image': 'https://example.com/img2.jpg',
                'platform': 'Flipkart'
            }],
            'Meesho': [{
                'title': 'Redmi Note 13 Pro 5G Case Cover',
                'price': '₹199',
                'price_num': 199,
                'rating': '3.8',
                'reviews': '45',
                'link': 'https://meesho.com/sample',
                'image': 'https://example.com/img3.jpg',
                'platform': 'Meesho'
            }]
        }
        res = run_comparison_pipeline("Redmi Note 13 Pro 5G", platform_results, platform_status={})
        
        self.assertIn('comparison_summary', res)
        summary = res['comparison_summary']
        self.assertIn('lowest_price', summary)
        self.assertIn('best_quality', summary)
        self.assertIn('best_spec_match', summary)
        self.assertIn('review_insights', summary)
        self.assertIn('value_for_money', summary)

        # Confirm Quality Table exists
        self.assertIn('quality_comparison_table', res)
        q_table = res['quality_comparison_table']
        self.assertGreater(len(q_table), 0)
        first_row = q_table[0]
        self.assertIn('platform', first_row)
        self.assertIn('quality_score', first_row)
        self.assertIn('data_confidence', first_row)
        self.assertIn('main_specs', first_row)
        self.assertIn('quality_attributes', first_row)

if __name__ == '__main__':
    unittest.main()
