import pandas as pd
import numpy as np
from pyrchidekt.api import getDeckById

def process_typeline(typeline):
    type_tags = []
    subtype_tags = []
    face_split = typeline.split('//')
    for face in face_split:
        type_split = face.split('—')
        type_tags += type_split[0].split(' ')
        if len(type_split) > 1:
            subtype_tags += type_split[1].split(' ')
    type_tags = sorted(list(set([f'type-{x.lower()}' for x in type_tags if x])))
    subtype_tags = sorted(list(set([f'subtype-{x.lower()}' for x in subtype_tags if x])))
    all_tags = type_tags + subtype_tags
    return all_tags

def load_card_database(filepath='data/oracle_data_webapp.f'):
    """Load and preprocess the card database."""
    oracle = pd.read_feather(filepath)
    oracle['img_url'] = oracle['image_uris'].apply(lambda x: x['normal'])
    oracle['oracle_tags'] = oracle['oracle_tags'].apply(lambda x: x.tolist())
    
    # Clean type line and create type tags
    oracle['type_tags'] = oracle['type_line'].apply(process_typeline)
    oracle['keyword_tags'] = oracle['keywords'].apply(lambda x: [f'keyword-{y.lower()}' for y in x if y])

    oracle['oracle_tags'] = oracle['oracle_tags'] + oracle['type_tags'] + oracle['keyword_tags']
    oracle['oracle_tags'] = oracle['oracle_tags'].apply(lambda x: sorted(list(set(x))))
    
    relevant_cols = ['oracle_id', 'name', 'color_identity', 'oracle_tags', 'img_url', 'scryfall_uri', 'edhrec_rank']
    return oracle[relevant_cols].set_index('name', drop=True)

def match_color_identity(ci, card_ci):
    """Check if a card's color identity matches the deck's color identity."""
    for c in card_ci:
        if c not in ci:
            return False
    return True

def score_tags(tag_score_dict, card_tags):
    """Calculate a card's score based on its tags."""
    score = 0
    for tag in card_tags:
        score += tag_score_dict.get(tag, 0)
    return int(score)

def clean_tags(tags):
    """Remove unwanted tags from the tag list."""
    tags = [tag for tag in tags if not tag.startswith('cycle')]
    tags = [tag for tag in tags if not tag.startswith('type-')]
    excl_tags = ['card-names', 'alliteration', 'single-english-word-name', 'namesake-spell']
    tags = [tag for tag in tags if tag not in excl_tags]
    return tags

class Deck:
    """Class to handle deck analysis and card recommendations."""
    
    def __init__(self, archidect_deck_id):
        self.archidect_deck = getDeckById(archidect_deck_id)
        if self.archidect_deck.format.name != 'COMMANDER_EDH':
            raise ValueError('Deck is not a commander deck')
        
        self._determine_commanders()
        self._determine_color_identity()
        self._determine_decklist()
        self._build_valid_card_pool()
    
    def _determine_commanders(self):
        """Identify the deck's commanders."""
        deck_categories = self.archidect_deck.categories
        commanders = []
        for category in deck_categories:
            if category.is_premier:
                commanders.extend([c.card.oracle_card.name for c in category.cards])
        self.commanders = card_db.loc[commanders]
        
    def _determine_color_identity(self):
        """Determine the deck's color identity."""
        color_identity = self.commanders['color_identity'].sum()
        self.color_identity = list(set(color_identity))
    
    def _determine_decklist(self):
        """Get the full decklist."""
        deck_categories = self.archidect_deck.categories
        decklist = []
        for category in deck_categories:
            if category.included_in_deck:
                decklist.extend([c.card.oracle_card.name for c in category.cards])
        decklist = list(set(decklist))
        self.decklist = card_db.loc[decklist]
        
    def _build_valid_card_pool(self):
        """Build pool of valid cards for recommendations."""
        card_pool = card_db[card_db.apply(lambda x: match_color_identity(self.color_identity, x['color_identity']), axis=1)]
        self.card_pool = card_pool.drop([i for i in self.decklist.index if i in card_pool.index])
            
    def analyze_tags(self):
        """Analyze tag frequency in the deck."""
        tags = self.decklist['oracle_tags'].sum()
        tags = clean_tags(tags)
        return pd.Series(tags).value_counts()
        
    def build_score_dict(self):
        """Build default scoring dictionary based on deck analysis."""
        tag_score_dict = self.analyze_tags().to_dict()
        tag_score_dict = {k: v for k, v in tag_score_dict.items() if v >= 1}
        return tag_score_dict
        
    def rank_cards(self, score_dict=None):
        """Rank cards based on tag scores."""
        if not score_dict:
            score_dict = self.build_score_dict()
        self.card_pool['score'] = self.card_pool['oracle_tags'].apply(lambda x: score_tags(score_dict, x))
        self.decklist['score'] = self.decklist['oracle_tags'].apply(lambda x: score_tags(score_dict, x))
        
        self.card_pool = self.card_pool.sort_values(['score', 'edhrec_rank'], ascending=[False, True])
        self.decklist = self.decklist.sort_values(['score', 'edhrec_rank'], ascending=[False, True])
        
        return self.decklist, self.card_pool

# Initialize global card database
card_db = load_card_database()