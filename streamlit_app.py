import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import base64
from io import BytesIO
import re

# Configure Streamlit page settings
st.set_page_config(
    page_title="SignForMe.AI",
    page_icon="✒️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom theme and styling
st.markdown("""
<style>
    /* Main container */
    .main {
        background-color: #f8f9fa;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #1f2937;
        font-family: 'Segoe UI', sans-serif;
    }
    
    /* Cards */
    div.stButton > button {
        width: 100%;
        border-radius: 8px;
        height: 2.5em;
    }
    
    /* Status badges */
    .status-badge {
        padding: 4px 12px;
        border-radius: 12px;
        font-weight: 500;
    }
    .status-pending {
        background-color: #fef3c7;
        color: #92400e;
    }
    .status-approved {
        background-color: #d1fae5;
        color: #065f46;
    }
    .status-rejected {
        background-color: #fee2e2;
        color: #991b1b;
    }
    
    /* Metrics */
    div[data-testid="stMetricValue"] {
        font-size: 24px;
        font-weight: 600;
    }
    
    /* Sidebar */
    .css-1d391kg {
        padding-top: 2rem;
    }
    
    /* Custom file uploader */
    .stFileUploader {
        padding: 1rem;
        border: 2px dashed #e5e7eb;
        border-radius: 8px;
        background-color: #ffffff;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state with enhanced structure
def init_session_state():
    if 'app_state' not in st.session_state:
        st.session_state.app_state = {
            'logged_in': False,
            'current_user': None,
            'selected_view': 'Dashboard',
            'dark_mode': False,
            'notifications': [],
            'last_activity': None
        }
    
    if 'data' not in st.session_state:
        st.session_state.data = {
            'documents': [],
            'comments': [],
            'tags': set(),
            'categories': [
                'Contract', 'Invoice', 'Report', 'Legal', 'HR', 'Financial', 'Other'
            ],
            'activities': [],
            'favorites': set(),
            'doc_id_counter': 1
        }
    
    if 'users' not in st.session_state:
        st.session_state.users = {
            'jimkalinov@gmail.com': {
                'password': 'Goldyear2023#*',
                'role': 'admin',
                'name': 'Jim Kalinov',
                'preferences': {
                    'notifications': True,
                    'theme': 'light',
                    'language': 'en',
                    'items_per_page': 10
                }
            },
            'userpal@example.com': {
                'password': 'System1234',
                'role': 'user',
                'name': 'User Pal',
                'preferences': {
                    'notifications': True,
                    'theme': 'light',
                    'language': 'en',
                    'items_per_page': 10
                }
            }
        }

# Enhanced status and action tracking
STATUS_BADGES = {
    'Pending': {
        'emoji': '⏳',
        'color': '#92400e',
        'bg_color': '#fef3c7',
        'label': 'Pending Review'
    },
    'Analyzing': {
        'emoji': '🔍',
        'color': '#1e40af',
        'bg_color': '#dbeafe',
        'label': 'Under Analysis'
    },
    'Authorized': {
        'emoji': '✅',
        'color': '#065f46',
        'bg_color': '#d1fae5',
        'label': 'Approved'
    },
    'Rejected': {
        'emoji': '❌',
        'color': '#991b1b',
        'bg_color': '#fee2e2',
        'label': 'Rejected'
    }
}

ACTIVITY_TYPES = {
    'upload': {'icon': '📤', 'color': '#2563eb'},
    'analyze': {'icon': '🔍', 'color': '#7c3aed'},
    'comment': {'icon': '💬', 'color': '#059669'},
    'approve': {'icon': '✅', 'color': '#16a34a'},
    'reject': {'icon': '❌', 'color': '#dc2626'},
    'tag': {'icon': '🏷️', 'color': '#d97706'},
    'login': {'icon': '🔑', 'color': '#475569'},
    'logout': {'icon': '🚪', 'color': '#475569'}
}

# Utility functions
def format_size(size_bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} GB"

def get_file_icon(file_type):
    """Return appropriate icon for file type"""
    if not file_type:
        return "📄"
    file_type = file_type.lower()
    if 'pdf' in file_type:
        return "📕"
    elif 'word' in file_type or 'docx' in file_type:
        return "📘"
    elif 'excel' in file_type or 'xlsx' in file_type:
        return "📗"
    elif 'image' in file_type:
        return "🖼️"
    elif 'text' in file_type:
        return "📝"
    return "📄"

def log_activity(activity_type, details, user_email, doc_id=None):
    """Log user activity with enhanced details"""
    activity = {
        'timestamp': datetime.now(),
        'type': activity_type,
        'details': details,
        'user': user_email,
        'doc_id': doc_id,
        'icon': ACTIVITY_TYPES[activity_type]['icon'],
        'color': ACTIVITY_TYPES[activity_type]['color']
    }
    st.session_state.data['activities'].insert(0, activity)
    
    # Update last activity
    st.session_state.app_state['last_activity'] = activity

def add_notification(message, type='info'):
    """Add a notification to the queue"""
    st.session_state.app_state['notifications'].append({
        'message': message,
        'type': type,
        'timestamp': datetime.now()
    })

# Initialize session state
init_session_state()

def extract_text_content(uploaded_file):
    """Enhanced text extraction with format detection"""
    try:
        content = uploaded_file.read()
        # Try to decode with different encodings
        for encoding in ['utf-8', 'latin-1', 'ascii']:
            try:
                text = content.decode(encoding)
                return {
                    'text': text,
                    'encoding': encoding,
                    'success': True,
                    'size': len(content)
                }
            except UnicodeDecodeError:
                continue
        
        # If no encoding worked, return basic info
        return {
            'text': str(content),
            'encoding': 'unknown',
            'success': False,
            'size': len(content)
        }
    except Exception as e:
        return {
            'text': '',
            'encoding': 'error',
            'success': False,
            'error': str(e),
            'size': 0
        }

def analyze_with_claude(text, context=None):
    """Enhanced document analysis with context awareness"""
    try:
        headers = {
            "x-api-key": st.secrets["CLAUDE_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        # Build context-aware prompt
        base_prompt = """Analyze this document content carefully. Provide a structured analysis with:

1. DOCUMENT TYPE: Identify the type and purpose of the document
2. KEY POINTS: Extract main facts and important information
3. NAMES & ENTITIES: List all person names and organizations
4. DATES & NUMBERS: Important dates, amounts, and numerical data
5. ACTION ITEMS: Any required actions or decisions
6. SUMMARY: Brief 2-3 sentence overview

Keep the analysis concise and focused on the most important details."""

        if context:
            base_prompt += f"\n\nAdditional context: {context}"

        data = {
            "model": "claude-3-opus-20240229",
            "messages": [
                {"role": "user", "content": f"{base_prompt}\n\nDocument content:\n{text}"}
            ],
            "max_tokens": 200,
            "temperature": 0.1
        }
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()['content'][0]['text']
            # Parse the analysis into structured format
            sections = {}
            current_section = None
            current_content = []
            
            for line in result.split('\n'):
                if line.strip() == '':
                    continue
                
                # Check if line is a section header
                for section in ['DOCUMENT TYPE:', 'KEY POINTS:', 'NAMES & ENTITIES:', 
                              'DATES & NUMBERS:', 'ACTION ITEMS:', 'SUMMARY:']:
                    if line.startswith(section):
                        if current_section:
                            sections[current_section] = '\n'.join(current_content)
                        current_section = section.replace(':', '')
                        current_content = []
                        break
                else:
                    if current_section:
                        current_content.append(line)
            
            # Add last section
            if current_section and current_content:
                sections[current_section] = '\n'.join(current_content)
            
            return {
                'success': True,
                'sections': sections,
                'raw_text': result,
                'timestamp': datetime.now()
            }
        else:
            return {
                'success': False,
                'error': f"API Error: {response.text}",
                'timestamp': datetime.now()
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'timestamp': datetime.now()
        }

def process_document(uploaded_file, user_email):
    """Enhanced document processing with metadata extraction"""
    doc_id = f"DOC{st.session_state.data['doc_id_counter']:04d}"
    upload_time = datetime.now()
    
    # Extract text content
    content_info = extract_text_content(uploaded_file)
    
    # Create document metadata
    doc_data = {
        'id': doc_id,
        'name': uploaded_file.name,
        'original_name': uploaded_file.name,
        'status': 'Pending',
        'upload_time': upload_time,
        'file_type': uploaded_file.type,
        'file_size': content_info['size'],
        'content': content_info['text'],
        'encoding': content_info['encoding'],
        'uploaded_by': user_email,
        'last_modified': upload_time,
        'tags': set(),
        'category': 'Other',
        'favorite': False,
        'comments': [],
        'analysis': None,
        'analysis_status': 'Not Started',
        'show_analysis': False,
        'metadata': {
            'extraction_success': content_info['success'],
            'processing_time': datetime.now() - upload_time
        }
    }
    
    # Add to documents list
    st.session_state.data['documents'].append(doc_data)
    st.session_state.data['doc_id_counter'] += 1
    
    # Log activity
    log_activity('upload', f"Uploaded document: {uploaded_file.name}", user_email, doc_id)
    
    # Send notification if user is not admin
    if st.session_state.users[user_email]['role'] != 'admin':
        subject = f"New Document Upload: {uploaded_file.name}"
        body = f"""
New document uploaded to SignForMe.AI

Document Details:
- Name: {uploaded_file.name}
- Type: {uploaded_file.type or 'Unknown'}
- Size: {format_size(content_info['size'])}
- Uploaded By: {st.session_state.users[user_email]['name']}
- Upload Time: {upload_time.strftime('%Y-%m-%d %H:%M:%S')}
- Document ID: {doc_id}

Please review this document in the system.
"""
        send_email_notification(subject, body)
    
    return doc_id

def analyze_document(doc_id):
    """Perform document analysis and update status"""
    doc = next((doc for doc in st.session_state.data['documents'] if doc['id'] == doc_id), None)
    if not doc:
        return False
    
    # Update status to analyzing
    doc['analysis_status'] = 'In Progress'
    doc['last_modified'] = datetime.now()
    
    # Perform analysis
    analysis_result = analyze_with_claude(doc['content'])
    
    if analysis_result['success']:
        doc['analysis'] = analysis_result
        doc['analysis_status'] = 'Completed'
        
        # Extract and add tags based on analysis
        if 'NAMES & ENTITIES' in analysis_result['sections']:
            names = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', 
                             analysis_result['sections']['NAMES & ENTITIES'])
            doc['tags'].update([name.lower() for name in names])
        
        # Try to determine document category
        doc_type = analysis_result['sections'].get('DOCUMENT TYPE', '').lower()
        for category in st.session_state.data['categories']:
            if category.lower() in doc_type:
                doc['category'] = category
                break
        
        log_activity('analyze', f"Analyzed document: {doc['name']}", 
                    st.session_state.app_state['current_user']['email'], doc_id)
        return True
    else:
        doc['analysis_status'] = 'Failed'
        return False

def send_email_notification(subject, body):
    """Enhanced email notification with HTML support and error handling"""
    try:
        sender_email = st.secrets["GMAIL_ADDRESS"]
        sender_password = st.secrets["GMAIL_APP_PASSWORD"]
        receiver_email = "jimkalinov@gmail.com"  # Admin email

        msg = MIMEMultipart('alternative')
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject

        # Create HTML version of the message
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2563eb;">{subject}</h2>
                    <div style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
                        {body.replace('\n', '<br>')}
                    </div>
                    <p style="color: #666; font-size: 12px; margin-top: 20px;">
                        This is an automated message from SignForMe.AI
                    </p>
                </div>
            </body>
        </html>
        """

        # Attach both plain text and HTML versions
        msg.attach(MIMEText(body, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))

        # Connect to SMTP server with error handling
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            return True
        except smtplib.SMTPAuthenticationError:
            st.error("Email authentication failed. Please check your credentials.")
            return False
        except smtplib.SMTPException as e:
            st.error(f"SMTP error occurred: {str(e)}")
            return False
        except Exception as e:
            st.error(f"Error sending email: {str(e)}")
            return False
            
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

def render_sidebar():
    """Render enhanced sidebar with navigation and quick actions"""
    with st.sidebar:
        st.image("https://via.placeholder.com/150x50.png?text=SignForMe.AI", use_column_width=True)
        st.divider()

        # User profile section
        with st.container():
            col1, col2 = st.columns([0.7, 0.3])
            with col1:
                st.write(f"👤 {st.session_state.app_state['current_user']['name']}")
            with col2:
                if st.button("🔄"):
                    st.rerun()

        # Main Navigation
        st.subheader("Navigation")
        nav_options = {
            "Dashboard": "🎯",
            "Documents": "📑",
            "Analytics": "📊",
            "Search": "🔍",
            "Settings": "⚙️"
        }

        for page, icon in nav_options.items():
            if st.sidebar.button(
                f"{icon} {page}",
                use_container_width=True,
                type="secondary" if st.session_state.app_state['selected_view'] != page else "primary"
            ):
                st.session_state.app_state['selected_view'] = page
                st.rerun()

        # Quick Actions
        st.sidebar.divider()
        st.sidebar.subheader("Quick Actions")
        
        # Upload button in sidebar
        if st.sidebar.button("📤 New Upload", use_container_width=True):
            st.session_state.app_state['selected_view'] = "Documents"
            st.rerun()

        # Recent Documents
        st.sidebar.divider()
        st.sidebar.subheader("Recent Documents")
        recent_docs = sorted(
            st.session_state.data['documents'],
            key=lambda x: x['upload_time'],
            reverse=True
        )[:5]

        for doc in recent_docs:
            with st.sidebar.container():
                st.write(f"{get_file_icon(doc['file_type'])} {doc['name'][:20]}...")
                st.caption(f"Status: {STATUS_BADGES[doc['status']]['emoji']} {doc['status']}")

        # Activity Feed
        st.sidebar.divider()
        st.sidebar.subheader("Recent Activity")
        recent_activities = st.session_state.data['activities'][:3]
        for activity in recent_activities:
            st.sidebar.write(
                f"{activity['icon']} {activity['details'][:30]}..."
            )

def render_document_card(doc):
    """Render an enhanced document card with actions"""
    with st.container():
        # Main card container with border and padding
        st.markdown("""
            <style>
            .doc-card {
                border: 1px solid #e5e7eb;
                border-radius: 8px;
                padding: 1rem;
                background-color: white;
                margin-bottom: 1rem;
            }
            </style>
        """, unsafe_allow_html=True)
        
        with st.container():
            # Header row
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.markdown(f"### {get_file_icon(doc['file_type'])} {doc['name']}")
                st.caption(f"Uploaded by {st.session_state.users[doc['uploaded_by']]['name']} on "
                          f"{doc['upload_time'].strftime('%Y-%m-%d %H:%M')}")
            
            with col2:
                st.markdown(f"""
                    <div class="status-badge status-{doc['status'].lower()}">
                        {STATUS_BADGES[doc['status']]['emoji']} {doc['status']}
                    </div>
                """, unsafe_allow_html=True)
            
            with col3:
                if st.button("⋮", key=f"menu_{doc['id']}"):
                    show_document_menu(doc)

            # Document metadata
            col1, col2, col3 = st.columns(3)
            with col1:
                st.caption(f"Size: {format_size(doc['file_size'])}")
            with col2:
                st.caption(f"Category: {doc['category']}")
            with col3:
                st.caption(f"Tags: {', '.join(doc['tags']) if doc['tags'] else 'No tags'}")

            # Analysis section
            if doc['analysis_status'] == 'Not Started':
                if st.button("🔍 Analyze Document", key=f"analyze_{doc['id']}"):
                    with st.spinner("Analyzing document..."):
                        if analyze_document(doc['id']):
                            st.success("Analysis completed!")
                            st.rerun()
                        else:
                            st.error("Analysis failed.")

            elif doc['analysis_status'] == 'Completed':
                with st.expander("📋 View Analysis"):
                    tabs = st.tabs([
                        "Summary", "Key Points", "Entities", "Data", "Actions"
                    ])
                    
                    analysis = doc['analysis']['sections']
                    with tabs[0]:
                        st.write(analysis.get('SUMMARY', 'No summary available'))
                    with tabs[1]:
                        st.write(analysis.get('KEY POINTS', 'No key points available'))
                    with tabs[2]:
                        st.write(analysis.get('NAMES & ENTITIES', 'No entities found'))
                    with tabs[3]:
                        st.write(analysis.get('DATES & NUMBERS', 'No data found'))
                    with tabs[4]:
                        st.write(analysis.get('ACTION ITEMS', 'No actions required'))

            # Actions row
            if doc['status'] == 'Pending' and st.session_state.app_state['current_user']['role'] == 'admin':
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✅ Approve", key=f"approve_{doc['id']}"):
                        update_document_status(doc, 'Authorized')
                        st.rerun()
                with col2:
                    if st.button("❌ Reject", key=f"reject_{doc['id']}"):
                        update_document_status(doc, 'Rejected')
                        st.rerun()

            # Comments section
            with st.expander("💬 Comments"):
                # Display existing comments
                for comment in doc['comments']:
                    st.text(f"{comment['user']}: {comment['text']}")
                    st.caption(f"{comment['timestamp'].strftime('%Y-%m-%d %H:%M')}")
                
                # Add new comment
                new_comment = st.text_input("Add a comment", key=f"comment_{doc['id']}")
                if st.button("Send", key=f"send_{doc['id']}"):
                    add_comment(doc['id'], new_comment)
                    st.rerun()

def show_document_menu(doc):
    """Show document actions menu"""
    with st.expander("Document Actions"):
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏷️ Edit Tags"):
                show_tag_editor(doc)
            if st.button("📋 Copy ID"):
                st.write(f"Document ID: {doc['id']}")
        with col2:
            if st.button("⭐ Favorite" if not doc['favorite'] else "☆ Unfavorite"):
                doc['favorite'] = not doc['favorite']
                st.rerun()
            if st.button("🗑️ Archive"):
                if st.warning("Are you sure?"):
                    archive_document(doc['id'])
                    st.rerun()

def show_tag_editor(doc):
    """Show tag editing interface"""
    with st.form(key=f"tags_{doc['id']}"):
        # Existing tags
        st.multiselect(
            "Select tags",
            list(st.session_state.data['tags']),
            default=list(doc['tags']),
            key=f"tag_select_{doc['id']}"
        )
        
        # Add new tag
        new_tag = st.text_input("Add new tag")
        
        if st.form_submit_button("Save Tags"):
            if new_tag:
                st.session_state.data['tags'].add(new_tag.lower())
                doc['tags'].add(new_tag.lower())
            st.rerun()

def add_comment(doc_id, text):
    """Add a comment to a document"""
    if not text.strip():
        return
    
    doc = next((doc for doc in st.session_state.data['documents'] if doc['id'] == doc_id), None)
    if doc:
        comment = {
            'user': st.session_state.app_state['current_user']['name'],
            'text': text,
            'timestamp': datetime.now()
        }
        doc['comments'].append(comment)
        log_activity('comment', f"Commented on {doc['name']}", 
                    st.session_state.app_state['current_user']['email'], doc_id)

def update_document_status(doc, new_status):
    """Update document status with notifications"""
    doc['status'] = new_status
    doc['last_modified'] = datetime.now()
    
    # Send email notification
    if doc['uploaded_by'] != st.session_state.app_state['current_user']['email']:
        subject = f"Document {new_status}: {doc['name']}"
        body = f"""
Your document status has been updated:

Document Name: {doc['name']}
New Status: {new_status}
Updated By: {st.session_state.app_state['current_user']['name']}
Update Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please check the system for more details.
"""
        send_email_notification(subject, body)
    
    # Log activity
    log_activity(
        'approve' if new_status == 'Authorized' else 'reject',
        f"{new_status} document: {doc['name']}",
        st.session_state.app_state['current_user']['email'],
        doc['id']
    )

def archive_document(doc_id):
    """Archive a document"""
    doc = next((doc for doc in st.session_state.data['documents'] if doc['id'] == doc_id), None)
    if doc:
        st.session_state.data['documents'].remove(doc)
        log_activity('archive', f"Archived document: {doc['name']}", 
                    st.session_state.app_state['current_user']['email'], doc_id)


def render_dashboard():
    """Render main dashboard with metrics and recent activity"""
    st.title("Dashboard 🎯")
    
    # Top metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    # Calculate metrics
    total_docs = len(st.session_state.data['documents'])
    pending_docs = len([d for d in st.session_state.data['documents'] if d['status'] == 'Pending'])
    analyzed_docs = len([d for d in st.session_state.data['documents'] if d['analysis_status'] == 'Completed'])
    
    with col1:
        st.metric(
            "Total Documents",
            total_docs,
            delta=f"{total_docs - pending_docs} processed"
        )
    
    with col2:
        st.metric(
            "Pending Review",
            pending_docs,
            delta=f"{pending_docs} remaining"
        )
    
    with col3:
        if total_docs > 0:
            approval_rate = len([d for d in st.session_state.data['documents'] 
                               if d['status'] == 'Authorized']) / total_docs * 100
            st.metric(
                "Approval Rate",
                f"{approval_rate:.1f}%",
                delta=f"{approval_rate - 50:.1f}% vs target"
            )
    
    with col4:
        st.metric(
            "Analyzed Documents",
            analyzed_docs,
            delta=f"{analyzed_docs}/{total_docs} analyzed"
        )

    # Main dashboard content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Recent Documents with Status
        st.subheader("Recent Documents")
        recent_docs = sorted(
            st.session_state.data['documents'],
            key=lambda x: x['upload_time'],
            reverse=True
        )[:5]
        
        if recent_docs:
            for doc in recent_docs:
                with st.container():
                    cols = st.columns([3, 2, 2, 1])
                    with cols[0]:
                        st.write(f"{get_file_icon(doc['file_type'])} {doc['name']}")
                    with cols[1]:
                        st.write(f"{STATUS_BADGES[doc['status']]['emoji']} {doc['status']}")
                    with cols[2]:
                        st.write(doc['upload_time'].strftime('%Y-%m-%d %H:%M'))
                    with cols[3]:
                        if st.button("View", key=f"view_{doc['id']}"):
                            st.session_state.app_state['selected_view'] = "Documents"
                            st.session_state.app_state['selected_doc'] = doc['id']
                            st.rerun()
        else:
            st.info("No documents yet")
    
    with col2:
        # Activity Feed
        st.subheader("Recent Activity")
        activities = st.session_state.data['activities'][:10]
        
        if activities:
            for activity in activities:
                with st.container():
                    st.markdown(f"""
                        <div style="padding: 5px 0;">
                            <span style="color: {activity['color']};">{activity['icon']}</span>
                            {activity['details']}<br>
                            <small style="color: #666;">
                                {activity['timestamp'].strftime('%Y-%m-%d %H:%M')}
                            </small>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No activity yet")

    # Bottom section with charts
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        # Document Status Distribution
        st.subheader("Document Status Distribution")
        status_counts = pd.DataFrame(
            [doc['status'] for doc in st.session_state.data['documents']],
            columns=['Status']
        ).value_counts()
        
        if not status_counts.empty:
            st.bar_chart(status_counts)
        else:
            st.info("No data for status distribution")
    
    with col2:
        # Analysis Progress
        st.subheader("Analysis Progress")
        analysis_status = pd.DataFrame(
            [doc['analysis_status'] for doc in st.session_state.data['documents']],
            columns=['Status']
        ).value_counts()
        
        if not analysis_status.empty:
            st.bar_chart(analysis_status)
        else:
            st.info("No data for analysis progress")

def render_analytics():
    """Render enhanced analytics page with interactive charts"""
    st.title("Analytics & Insights 📊")
    
    # Time period selector
    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox(
            "Time Period",
            ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"],
            index=1
        )
    with col2:
        if st.button("Export Report"):
            generate_analytics_report()
    
    # Calculate date range
    end_date = datetime.now()
    if period == "Last 7 Days":
        start_date = end_date - timedelta(days=7)
    elif period == "Last 30 Days":
        start_date = end_date - timedelta(days=30)
    elif period == "Last 90 Days":
        start_date = end_date - timedelta(days=90)
    else:
        start_date = datetime.min
    
    # Filter documents by date range
    filtered_docs = [
        doc for doc in st.session_state.data['documents']
        if start_date <= doc['upload_time'] <= end_date
    ]
    
    # Analytics tabs
    tabs = st.tabs([
        "Document Analytics",
        "User Activity",
        "Processing Times",
        "Category Analysis"
    ])
    
    with tabs[0]:
        col1, col2 = st.columns(2)
        with col1:
            # Document Status Trend
            st.subheader("Document Status Trend")
            status_df = pd.DataFrame([
                {
                    'date': doc['upload_time'].date(),
                    'status': doc['status']
                }
                for doc in filtered_docs
            ])
            if not status_df.empty:
                pivot_df = pd.pivot_table(
                    status_df,
                    index='date',
                    columns='status',
                    aggfunc='size',
                    fill_value=0
                )
                st.line_chart(pivot_df)
            else:
                st.info("No data available for selected period")
        
        with col2:
            # Analysis Progress
            st.subheader("Analysis Completion Rate")
            analysis_df = pd.DataFrame([
                {
                    'date': doc['upload_time'].date(),
                    'analyzed': doc['analysis_status'] == 'Completed'
                }
                for doc in filtered_docs
            ])
            if not analysis_df.empty:
                daily_rate = analysis_df.groupby('date')['analyzed'].mean()
                st.line_chart(daily_rate)
            else:
                st.info("No data available for selected period")
    
    with tabs[1]:
        # User Activity Analysis
        st.subheader("User Activity")
        
        activity_df = pd.DataFrame(
            [activity for activity in st.session_state.data['activities']
             if start_date <= activity['timestamp'] <= end_date]
        )
        
        if not activity_df.empty:
            col1, col2 = st.columns(2)
            with col1:
                # Activity by User
                user_activity = activity_df['user'].value_counts()
                st.bar_chart(user_activity)
            
            with col2:
                # Activity by Type
                type_activity = activity_df['type'].value_counts()
                st.bar_chart(type_activity)
        else:
            st.info("No activity data available for selected period")
    
    with tabs[2]:
        # Processing Time Analysis
        st.subheader("Document Processing Times")
        
        processing_times = [
            {
                'document': doc['name'],
                'upload_to_analysis': (
                    doc['analysis']['timestamp'] - doc['upload_time']
                ).total_seconds() / 60 if doc.get('analysis') else 0,
                'total_processing': (
                    datetime.now() - doc['upload_time']
                ).total_seconds() / 60
            }
            for doc in filtered_docs
        ]
        
        if processing_times:
            df_times = pd.DataFrame(processing_times)
            st.bar_chart(df_times[['upload_to_analysis', 'total_processing']])
        else:
            st.info("No processing time data available")
    
    with tabs[3]:
        # Category and Tag Analysis
        st.subheader("Document Categories")
        
        category_df = pd.DataFrame([
            {
                'category': doc['category'],
                'count': 1
            }
            for doc in filtered_docs
        ])
        
        if not category_df.empty:
            category_counts = category_df.groupby('category')['count'].sum()
            st.bar_chart(category_counts)
            
            # Tag Cloud
            st.subheader("Popular Tags")
            all_tags = [tag for doc in filtered_docs for tag in doc['tags']]
            if all_tags:
                tag_counts = pd.Series(all_tags).value_counts()
                st.bar_chart(tag_counts)
            else:
                st.info("No tags found in documents")
        else:
            st.info("No category data available")

def generate_analytics_report():
    """Generate and download comprehensive analytics report"""
    report_data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "generated_by": st.session_state.app_state['current_user']['name'],
        "metrics": {
            "total_documents": len(st.session_state.data['documents']),
            "status_distribution": {
                status: len([d for d in st.session_state.data['documents'] if d['status'] == status])
                for status in set(d['status'] for d in st.session_state.data['documents'])
            },
            "analysis_status": {
                status: len([d for d in st.session_state.data['documents'] if d['analysis_status'] == status])
                for status in set(d['analysis_status'] for d in st.session_state.data['documents'])
            },
            "user_activity": {
                user['name']: len([d for d in st.session_state.data['documents'] if d['uploaded_by'] == email])
                for email, user in st.session_state.users.items()
            }
        }
    }
    
    # Convert to DataFrame for CSV export
    df = pd.DataFrame([
        {
            'Document ID': doc['id'],
            'Name': doc['name'],
            'Status': doc['status'],
            'Upload Time': doc['upload_time'],
            'Category': doc['category'],
            'Tags': ', '.join(doc['tags']),
            'Uploaded By': st.session_state.users[doc['uploaded_by']]['name'],
            'Analysis Status': doc['analysis_status']
        }
        for doc in st.session_state.data['documents']
    ])
    
    csv = df.to_csv(index=False)
    st.download_button(
        "📥 Download Report",
        csv,
        "analytics_report.csv",
        "text/csv",
        key='download-report'
    )


def render_search():
    """Render streamlined search interface"""
    st.title("Search Documents 🔍")
    
    # Search bar and filters
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            label="Search documents",
            placeholder="Enter keywords, names, or document ID"
        )
    with col2:
        search_in = st.selectbox(
            label="Search in",
            options=["All", "Content", "Names", "Comments"]
        )

    # Filters in a cleaner layout
    with st.expander("Filters"):
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.multiselect(
                label="Status",
                options=list(STATUS_BADGES.keys())
            )
            date_range = st.date_input(
                label="Date Range",
                value=[datetime.now() - timedelta(days=30), datetime.now()]
            )
        with col2:
            uploader_filter = st.multiselect(
                label="Uploaded By",
                options=[user['name'] for user in st.session_state.users.values()]
            )
            category_filter = st.multiselect(
                label="Category",
                options=["Contract", "Invoice", "Report", "Legal", "HR", "Financial", "Other"]
            )

    # Execute search
    if search_query or status_filter or category_filter:
        results = search_documents(
            search_query, search_in, status_filter, 
            category_filter, date_range, uploader_filter
        )
        
        # Display results
        st.subheader(f"Results ({len(results)} documents)")
        
        if results:
            sort_by = st.selectbox(
                label="Sort by",
                options=["Newest", "Oldest", "Name"]
            )
            sorted_results = sort_results(results, sort_by)
            
            for doc in sorted_results:
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1])
                    with col1:
                        st.write(f"{get_file_icon(doc['file_type'])} {doc['name']}")
                        st.caption(f"Uploaded: {doc['upload_time'].strftime('%Y-%m-%d %H:%M')}")
                    with col2:
                        st.write(f"{STATUS_BADGES[doc['status']]['emoji']} {doc['status']}")
                    with col3:
                        if st.button(
                            label=f"View {doc['id']}", 
                            key=f"view_{doc['id']}"
                        ):
                            st.session_state['selected_view'] = "Documents"
                            st.session_state['selected_doc'] = doc['id']
                            st.experimental_rerun()  # Changed to experimental_rerun
                st.divider()
        else:
            st.info("No matching documents found")

def render_settings():
    """Render settings interface"""
    st.title("Settings ⚙️")
    
    # Settings tabs
    tab1, tab2 = st.tabs(["User Settings", "System Settings"])
    
    with tab1:
        st.subheader("User Preferences")
        user_email = st.session_state['current_user']['email']
        user = st.session_state.users[user_email]
        
        # Interface settings
        st.write("### Interface")
        col1, col2 = st.columns(2)
        with col1:
            theme = st.selectbox(
                label="Theme",
                options=["Light", "Dark"],
                index=0 if user.get('theme') == 'light' else 1
            )
            show_previews = st.checkbox(
                label="Show document previews",
                value=user.get('show_previews', True)
            )
        with col2:
            items_per_page = st.number_input(
                label="Items per page",
                min_value=5,
                max_value=50,
                value=user.get('items_per_page', 10)
            )
        
        # Notification settings
        st.write("### Notifications")
        email_notifications = st.checkbox(
            label="Email notifications",
            value=user.get('email_notifications', True)
        )
        
        if st.button(label="Save User Settings"):
            user.update({
                'theme': theme.lower(),
                'show_previews': show_previews,
                'items_per_page': items_per_page,
                'email_notifications': email_notifications
            })
            st.success("Settings saved!")
    
    with tab2:
        if st.session_state['current_user']['role'] == 'admin':
            st.subheader("System Configuration")
            
            # Document settings
            st.write("### Document Settings")
            max_file_size = st.number_input(
                label="Maximum file size (MB)",
                min_value=1,
                max_value=100,
                value=50
            )
            retention_days = st.number_input(
                label="Document retention (days)",
                min_value=1,
                max_value=365,
                value=30
            )
            
            # Categories
            st.write("### Categories")
            categories = st.multiselect(
                label="Document Categories",
                options=["Contract", "Invoice", "Report", "Legal", "HR", "Financial", "Other"],
                default=st.session_state.data.get('categories', [])
            )
            
            new_category = st.text_input(label="Add new category")
            if new_category and st.button(label="Add Category"):
                categories.append(new_category)
                st.success(f"Added category: {new_category}")
            
            if st.button(label="Save System Settings"):
                st.session_state.data['categories'] = categories
                st.session_state.data['max_file_size'] = max_file_size
                st.session_state.data['retention_days'] = retention_days
                st.success("System settings saved!")
        else:
            st.info("System settings are only available to administrators")

def main():
    if 'current_user' in st.session_state:
        if st.session_state['selected_view'] == "Search":
            render_search()
        elif st.session_state['selected_view'] == "Settings":
            render_settings()
    else:
        st.error("Please log in to access this feature.")

if __name__ == "__main__":
    main()
