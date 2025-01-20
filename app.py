import streamlit as st
import re
import json
import pandas as pd
from collections import OrderedDict
from cardrec import card_db, Deck

# Page config
st.set_page_config(page_title="EDH TagRec", layout="wide")
st.title("MTG Commander - Tag-based Recommender")

# Initialize session state for interface mode if not exists
if 'interface_mode' not in st.session_state:
    st.session_state.interface_mode = 'visual'
if 'deck_input_mode' not in st.session_state:
    st.session_state.deck_input_mode = 'url'

# Get all unique tags from the database
@st.cache_data
def get_all_tags():
    all_tags = set()
    for tags in card_db['oracle_tags']:
        all_tags.update(tags)
    return sorted(list(all_tags))

# Sidebar inputs
with st.sidebar:
    st.header("Configuration")
    # Archidekt URL input
    deck_url = st.text_input(
        "Archidekt Deck URL",
        placeholder="https://archidekt.com/decks/10141244"
    )
    
    # Extract deck ID from URL
    deck_id = None
    if deck_url:
        match = re.search(r'/(\d+)', deck_url)
        if match:
            deck_id = int(match.group(1))
            
            # Initialize deck and tag scores when URL is first entered
            if 'deck' not in st.session_state or st.session_state.get('current_deck_id') != deck_id:
                try:
                    st.session_state.deck = Deck(deck_id)
                    # Get top 10 tags and their weights
                    initial_scores = st.session_state.deck.build_score_dict()
                    # Convert to OrderedDict and take top 10
                    ordered_scores = OrderedDict(
                        sorted(initial_scores.items(), key=lambda x: x[1], reverse=True)[:10]
                    )
                    st.session_state.initial_scores = ordered_scores
                    st.session_state.tag_scores = ordered_scores
                    st.session_state.current_deck_id = deck_id
                except Exception as e:
                    st.error(f"Error loading deck: {str(e)}")
                    deck_id = None

    if deck_id and hasattr(st.session_state, 'deck'):
        
        col1, col2, col3 = st.columns(3)
        i = 0
        for name, card in st.session_state.deck.commanders.iterrows():
            if i % 3 == 0:
                col1.image(card['img_url'], width=300)
            elif i % 3 == 1:
                col2.image(card['img_url'], width=300)
            else:
                col3.image(card['img_url'], width=300)
            i += 1
        
        # Tag Scoring Interface
        st.subheader("Tag Scoring")
        
        # Interface mode toggle
        mode = st.radio(
            "Interface Mode",
            options=['Visual Editor', 'JSON Editor'],
            horizontal=True,
            key='interface_mode_toggle'
        )
        
        if mode == 'JSON Editor':
            # JSON editing interface
            json_str = st.text_area(
                "Edit tag scores (JSON format)",
                value=json.dumps(st.session_state.tag_scores, indent=2),
                height=400,
                key='json_editor'
            )
            
            try:
                new_scores = json.loads(json_str)
                if isinstance(new_scores, dict) and all(isinstance(v, (int, float)) for v in new_scores.values()):
                    st.session_state.tag_scores = OrderedDict(new_scores)
                else:
                    st.error("Invalid format. All values must be numbers.")
            except json.JSONDecodeError:
                st.error("Invalid JSON format")
                
        else:
            # Visual editing interface
            # Container for existing tags
            with st.container():
                st.caption("Existing Tags")
                to_delete = []  # Track tags to delete
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button('Clear'):
                        st.session_state.tag_scores = OrderedDict()
                with col2:
                    if st.button('Reset'):
                        st.session_state.tag_scores = st.session_state.initial_scores
                with col3:
                    if st.button('Standard'):
                        st.session_state.tag_scores = OrderedDict({
                            'ramp': 1,
                            'draw': 1,
                            'card-advantage': 1,
                            'protect'
                            'removal': 1,
                            'tutor': 1,
                            'recursion': 1,
                            'protects-permanent': 1,
                            'sweeper': 1
                        })
                
                # Display existing tags with their scores
                for tag, score in st.session_state.tag_scores.items():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.text(tag)
                    with col2:
                        new_score = st.number_input(
                            f"Score for {tag}",
                            value=float(score),
                            key=f"score_{tag}",
                            label_visibility="collapsed",
                            step=1.0
                        )
                        st.session_state.tag_scores[tag] = new_score
                    with col3:
                        if st.button("🗑️", key=f"delete_{tag}", help=f"Delete {tag}"):
                            to_delete.append(tag)
            
            # Remove deleted tags
            for tag in to_delete:
                del st.session_state.tag_scores[tag]
            
            # Add new tag interface
            st.header('Add tag')

            # Get available tags (excluding already used ones)
            all_tags = get_all_tags()
            available_tags = [tag for tag in all_tags if tag not in st.session_state.tag_scores]
            
            col1, col2 = st.columns([3, 2])
            with col1:
                # Use selectbox for tag selection
                new_tag = st.selectbox(
                    "Select or search for a tag",
                    options=[""] + available_tags,
                )
            
            with col2:
                new_score = st.number_input("Score", value=1, key="new_score", step=1)
            
            if st.button("Add Tag") and new_tag:
                if new_tag in st.session_state.tag_scores:
                    st.warning(f"Tag '{new_tag}' already exists!")
                else:
                    # Add new tag while maintaining order
                    new_scores = OrderedDict(st.session_state.tag_scores)
                    new_scores[new_tag] = new_score
                    st.session_state.tag_scores = new_scores
                    st.rerun()
        
        # Display options
        st.subheader("Display Options")
        #num_cards = st.slider("Number of cards to display", 1, 100, 30)
        st.session_state.include_deck_cards = st.checkbox("Include cards already in deck", value=False)
        st.session_state.cards_per_row = st.slider("Cards per row", 1, 6, 3)
        st.session_state.total_rows = st.slider("Total rows", 1, 50, 25)

# Main content
if deck_id and hasattr(st.session_state, 'deck'):
    try:
        decklist, card_pool = st.session_state.deck.rank_cards(st.session_state.tag_scores)
        if st.session_state.include_deck_cards:
            card_pool = pd.concat([card_pool, decklist])
            card_pool = card_pool.sort_values(['score', 'edhrec_rank'], ascending=[False, True])
        card_pool = card_pool[card_pool['score'] > 0]
        
        if len(card_pool) > 0:
            
            # Display recommendations in a grid
            st.header("Recommended Cards")
            
            # Function to get relevant tags for a card
            def get_relevant_tags(card_tags):
                return [tag for tag in card_tags if tag in st.session_state.tag_scores]
            
            # Create rows of cards
            for i in range(0, min(st.session_state.cards_per_row*st.session_state.total_rows, len(card_pool)), st.session_state.cards_per_row):
                cols = st.columns(st.session_state.cards_per_row)
                for j, col in enumerate(cols):
                    if i + j < min(st.session_state.cards_per_row*st.session_state.total_rows, len(card_pool)):
                        card = card_pool.iloc[i + j]
                        with col:
                            # Get relevant tags for this card
                            relevant_tags = get_relevant_tags(card['oracle_tags'])
                            tag_text = "\nRelevant tags:\n• " + "\n• ".join(relevant_tags) if relevant_tags else "\nNo matching tags"
                            score = card['score']
                            
                            # Create clickable image with tooltip
                            st.markdown(f'''
                                <a href="{card['scryfall_uri']}" target="_blank" title="{card.name}\nScore: {score:.0f}{tag_text}">
                                    <img src="{card['img_url']}" width="100%">
                                </a>
                                ''', 
                                unsafe_allow_html=True
                            )
                            #st.caption(f"{card.name} (Score: {card['score']:.1f})")
            
    except Exception as e:
        st.error(f"Error processing deck: {str(e)}")
else:
    st.info("Enter an Archidekt deck URL to get started!")