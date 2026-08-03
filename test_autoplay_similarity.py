import unittest
import re

class TestSimilarity(unittest.TestCase):
    def is_too_similar(self, title1, title2):
        if not title1 or not title2: return False
        
        def clean(t):
            t = t.lower()
            t = re.sub(r'\(.*?\)', '', t)
            t = re.sub(r'\[.*?\]', '', t)
            t = re.sub(r'[^\w\s]', '', t)
            fluff = {'official', 'video', 'music', 'lyrics', 'audio', 'hd', '4k', 'live', 'full', 'version', 'hq', 'extended', 'remix', 'cover', 'acoustic', 'instrumental'}
            words = [w for w in t.split() if w not in fluff]
            return set(words)
            
        s1 = clean(title1)
        s2 = clean(title2)
        
        if not s1 or not s2: return False
        
        common = s1.intersection(s2)
        largest = max(len(s1), len(s2))
        ratio = len(common) / largest if largest > 0 else 0
        return ratio >= 0.7

    def test_versions(self):
        t1 = "The Weeknd - Blinding Lights (Official Video)"
        t2 = "The Weeknd - Blinding Lights (Lyrics)"
        self.assertTrue(self.is_too_similar(t1, t2))
        
        t3 = "The Weeknd - Blinding Lights (Remix)"
        self.assertTrue(self.is_too_similar(t1, t3))

    def test_different_songs(self):
        t1 = "The Weeknd - Blinding Lights"
        t2 = "The Weeknd - Save Your Tears"
        self.assertFalse(self.is_too_similar(t1, t2))

    def test_same_artist_different_track(self):
        t1 = "Dua Lipa - Levitating"
        t2 = "Dua Lipa - Don't Start Now"
        self.assertFalse(self.is_too_similar(t1, t2))

    def test_different_artists_same_title_start(self):
        t1 = "Hello by Adele"
        t2 = "Hello by Lionel Richie"
        self.assertFalse(self.is_too_similar(t1, t2))

    def test_short_titles(self):
        t1 = "Low"
        t2 = "Low Remix"
        self.assertTrue(self.is_too_similar(t1, t2))

if __name__ == '__main__':
    unittest.main()
