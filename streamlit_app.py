import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta, date
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'documents' not in st.session_state:
    st.session_state['documents'] = []
if 'pending_analysis' not in st.session_state:
    st.session_state['pending_analysis'] = []
if 'history' not in st.session_state:
    st.session_state['history'] = []
if 'doc_id_counter' not in st.session_state:
    st.session_state['doc_id_counter'] = 1
if 'document_removal_times' not in st.session_state:
    st.session_state['document_removal_times'] = {}
if 'action_times' not in st.session_state:
    st.session_state['action_times'] = []
if 'selected_view' not in st.session_state:
    st.session_state['selected_view'] = 'Upload'
if 'user_actions' not in st.session_state:
    st.session_state['user_actions'] = []
if 'analyzed_docs' not in st.session_state:
    st.session_state['analyzed_docs'] = set()
if 'users' not in st.session_state:
    st.session_state['users'] = {
        'maxhaiti@aol.com': {
            'password': 'Admin123',
            'role': 'admin',
            'name': 'Maxi Raymonville'
        },
        'userpal@example.com': {
            'password': 'System1234',
            'role': 'user',
            'name': 'User Pal'
        }
    }
if 'current_user' not in st.session_state:
    st.session_state['current_user'] = None

STATUS_EMOJIS = {
    'Pending': '⏳',
    'Authorized': '✅',
    'Rejected': '❌',
    'Processing': '🔄',
    'Analyzed': '🔍'
}

def send_email_notification(subject, body):
    try:
        sender_email = st.secrets["GMAIL_ADDRESS"]
        sender_password = st.secrets["GMAIL_APP_PASSWORD"]
        receiver_email = "jimkalinov@gmail.com"  # Admin email

        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = receiver_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Failed to send email: {str(e)}")
        return False

def extract_text_content(uploaded_file):
    """Attempt to extract text content from uploaded file"""
    try:
        content = uploaded_file.read()
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError:
            return content.decode('latin-1')
    except Exception as e:
        st.warning(f"Note: File content might not be perfectly extracted. Proceeding with best effort.")
        return str(content)

def analyze_with_claude(text):
    try:
        headers = {
            "x-api-key": st.secrets["CLAUDE_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        prompt = """Brief summary of the document (max 2-3 sentences)

Please keep the response concise and focused.

Document content:
{text}"""
        
        data = {
            "model": "claude-3-opus-20240229",
            "messages": [
                {"role": "user", "content": prompt.format(text=text)}
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
            return response.json()['content'][0]['text']
        else:
            st.error(f"API Error: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error: {str(e)}")
        return None

def login_user(email, password):
    if email in st.session_state['users']:
        user = st.session_state['users'][email]
        if password == user['password']:
            st.session_state['current_user'] = {
                'email': email,
                'role': user['role'],
                'name': user['name']
            }
            return True
    return False

def log_user_action(action, details):
    st.session_state['user_actions'].append({
        'timestamp': datetime.now(),
        'action': action,
        'details': details,
        'user': st.session_state['current_user']['email']
    })

def check_expired_items():
    current_time = datetime.now()
    for doc_id, expiration_time in list(st.session_state['document_removal_times'].items()):
        if current_time > expiration_time:
            st.session_state['documents'] = [doc for doc in st.session_state['documents'] if doc['id'] != doc_id]
            del st.session_state['document_removal_times'][doc_id]

def handle_document_upload(uploaded_file, user_email):
    doc_id = f"SIGN{st.session_state['doc_id_counter']:03d}"
    upload_time = datetime.now()
    
    # Create document data
    doc_data = {
        'id': doc_id,
        'name': uploaded_file.name,
        'status': 'Pending',
        'upload_time': upload_time,
        'file_type': uploaded_file.type,
        'file_size': uploaded_file.size,
        'content': extract_text_content(uploaded_file),
        'analysis': None,
        'uploaded_by': user_email,
        'show_analysis': False  # New field for toggle state
    }
    
    # Add to documents list
    st.session_state['documents'].append(doc_data)
    
    # Add to history
    st.session_state['history'].append({
        'date': upload_time.strftime("%Y-%m-%d %H:%M:%S"),
        'id': doc_id,
        'name': uploaded_file.name,
        'status': f"Pending {STATUS_EMOJIS['Pending']}",
        'analysis': None,
        'uploaded_by': user_email
    })
    
    # Send email notification if uploaded by a regular user
    if st.session_state['users'][user_email]['role'] != 'admin':
        subject = f"New Document Upload: {uploaded_file.name}"
        body = f"""
A new document has been uploaded:

Document Name: {uploaded_file.name}
Uploaded By: {st.session_state['users'][user_email]['name']} ({user_email})
Upload Time: {upload_time.strftime('%Y-%m-%d %H:%M:%S')}
Document ID: {doc_id}

Please review this document in the system.
"""
        send_email_notification(subject, body)
    
    log_user_action('upload', f"Document uploaded by {user_email}: {uploaded_file.name}")
    return doc_id

def analyze_document(doc):
    """Analyze a single document and update its analysis"""
    if doc['id'] in st.session_state['analyzed_docs']:
        return False
    
    analysis = analyze_with_claude(doc['content'])
    if analysis:
        # Update document with analysis
        for stored_doc in st.session_state['documents']:
            if stored_doc['id'] == doc['id']:
                stored_doc['analysis'] = analysis
                break
        
        # Update history
        for hist_doc in st.session_state['history']:
            if hist_doc['id'] == doc['id']:
                hist_doc['analysis'] = analysis
        
        # Mark as analyzed
        st.session_state['analyzed_docs'].add(doc['id'])
        
        # Send email notification for analysis completion
        if doc['uploaded_by'] != st.session_state['current_user']['email']:
            subject = f"Document Analysis Completed: {doc['name']}"
            body = f"""
Document analysis has been completed:

Document Name: {doc['name']}
Analyzed By: {st.session_state['current_user']['name']}
Analysis Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Document ID: {doc['id']}

Please check the analysis results in the system.
"""
            send_email_notification(subject, body)
        
        log_user_action('analyze', f"Analyzed document: {doc['name']}")
        return True
    return False

def show_document_card(doc):
    """Display a single document card with analysis toggle"""
    with st.container():
        # Document header
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"📄 {doc['name']} | Status: {doc['status']} {STATUS_EMOJIS[doc['status']]}")
            st.caption(f"Uploaded: {doc['upload_time'].strftime('%Y-%m-%d %H:%M:%S')}")
            if st.session_state['current_user']['role'] == 'admin':
                st.caption(f"Uploaded by: {st.session_state['users'][doc['uploaded_by']]['name']}")
        
        # Analysis section
        if doc.get('analysis'):
            # Toggle for analysis
            if st.button("🔍 Toggle Analysis", key=f"toggle_{doc['id']}"):
                doc['show_analysis'] = not doc.get('show_analysis', False)
            
            # Show analysis if toggled
            if doc.get('show_analysis', False):
                with st.container():
                    st.markdown("### Analysis Results")
                    sections = doc['analysis'].split('\n')
                    for section in sections:
                        if any(header in section for header in [
                            "KEY POINTS:", "NAMES:", "DOCUMENT TYPE:",
                            "DATES & NUMBERS:", "SUMMARY:"
                        ]):
                            st.markdown(f"**{section}**")
                        elif section.strip():
                            st.write(section)
        
        st.divider()

def show_upload_section():
    st.header("Upload Documents 📤")
    
    # File uploader
    uploaded_files = st.file_uploader("Choose files", type=None, accept_multiple_files=True)
    
    if uploaded_files:
        with st.spinner("Processing uploads..."):
            for uploaded_file in uploaded_files:
                doc_id = handle_document_upload(uploaded_file, st.session_state['current_user']['email'])
                st.session_state['doc_id_counter'] += 1
            
        st.success(f"Successfully uploaded {len(uploaded_files)} document(s)!")

    # Show unanalyzed documents
    unanalyzed_docs = [doc for doc in st.session_state['documents'] 
                      if doc['id'] not in st.session_state['analyzed_docs']]
    
    if unanalyzed_docs:
        st.subheader("Documents Available for Analysis")
        
        for doc in unanalyzed_docs:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(f"📄 {doc['name']} ({doc['file_type'] or 'unknown type'}) - {doc['file_size']/1024:.1f} KB")
            with col2:
                if st.button("🔍 Analyze", key=f"analyze_{doc['id']}"):
                    with st.spinner(f"Analyzing {doc['name']}..."):
                        if analyze_document(doc):
                            st.success("Analysis completed!")
                            st.rerun()
                        else:
                            st.error("Analysis failed.")

def show_status_section():
    st.header("Document Status 📋")
    check_expired_items()
    
    # Filter options
    col1, col2 = st.columns([2, 2])
    with col1:
        status_filter = st.selectbox("Filter by status", ["All", "Pending", "Authorized", "Rejected"])
    with col2:
        if st.session_state['current_user']['role'] == 'admin':
            user_filter = st.selectbox(
                "Filter by user",
                ["All Users"] + [user['name'] for user in st.session_state['users'].values()]
            )
    
    filtered_docs = st.session_state['documents']
    if status_filter != "All":
        filtered_docs = [doc for doc in filtered_docs if doc['status'] == status_filter]
    
    if st.session_state['current_user']['role'] == 'admin' and user_filter != "All Users":
        user_email = [email for email, user in st.session_state['users'].items() 
                     if user['name'] == user_filter][0]
        filtered_docs = [doc for doc in filtered_docs if doc.get('uploaded_by') == user_email]
    elif st.session_state['current_user']['role'] != 'admin':
        # Regular users can only see their own documents
        filtered_docs = [doc for doc in filtered_docs 
                        if doc.get('uploaded_by') == st.session_state['current_user']['email']]
    
    if filtered_docs:
        for doc in filtered_docs:
            with st.container():
                # Document header and main info
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"📄 {doc['name']} | Status: {doc['status']} {STATUS_EMOJIS[doc['status']]}")
                    st.caption(f"Uploaded: {doc['upload_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                    if st.session_state['current_user']['role'] == 'admin':
                        st.caption(f"Uploaded by: {st.session_state['users'][doc['uploaded_by']]['name']}")
                
                # Action buttons for pending documents
                if doc['status'] == 'Pending' and st.session_state['current_user']['role'] == 'admin':
                    with col2:
                        if st.button(f"Accept", key=f"accept_{doc['id']}"):
                            doc['status'] = "Authorized"
                            action_time = datetime.now()
                            
                            # Update history
                            for hist_doc in st.session_state['history']:
                                if hist_doc['id'] == doc['id']:
                                    hist_doc['status'] = f"Authorized {STATUS_EMOJIS['Authorized']}"
                                    hist_doc['date'] = action_time.strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Send email notification
                            if doc['uploaded_by'] != st.session_state['current_user']['email']:
                                subject = f"Document Approved: {doc['name']}"
                                body = f"""
Your document has been approved:

Document Name: {doc['name']}
Approved By: {st.session_state['current_user']['name']}
Approval Time: {action_time.strftime('%Y-%m-%d %H:%M:%S')}
Document ID: {doc['id']}

You can check the status in the system.
"""
                                send_email_notification(subject, body)
                            
                            st.session_state['action_times'].append((doc['upload_time'], action_time))
                            log_user_action('authorize', f"Authorized document: {doc['name']}")
                            st.rerun()
                    
                    with col3:
                        if st.button(f"Reject", key=f"reject_{doc['id']}"):
                            doc['status'] = "Rejected"
                            action_time = datetime.now()
                            
                            # Update history
                            for hist_doc in st.session_state['history']:
                                if hist_doc['id'] == doc['id']:
                                    hist_doc['status'] = f"Rejected {STATUS_EMOJIS['Rejected']}"
                                    hist_doc['date'] = action_time.strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Send email notification
                            if doc['uploaded_by'] != st.session_state['current_user']['email']:
                                subject = f"Document Rejected: {doc['name']}"
                                body = f"""
Your document has been rejected:

Document Name: {doc['name']}
Rejected By: {st.session_state['current_user']['name']}
Rejection Time: {action_time.strftime('%Y-%m-%d %H:%M:%S')}
Document ID: {doc['id']}

Please check the status in the system for more information.
"""
                                send_email_notification(subject, body)
                            
                            st.session_state['action_times'].append((doc['upload_time'], action_time))
                            log_user_action('reject', f"Rejected document: {doc['name']}")
                            st.rerun()
                
                # Analysis section with toggle
                if doc.get('analysis'):
                    if st.button("🔍 Toggle Analysis", key=f"toggle_status_{doc['id']}"):
                        doc['show_analysis'] = not doc.get('show_analysis', False)
                    
                    if doc.get('show_analysis', False):
                        with st.container():
                            st.markdown("### Analysis Results")
                            sections = doc['analysis'].split('\n')
                            for section in sections:
                                if any(header in section for header in [
                                    "KEY POINTS:", "NAMES:", "DOCUMENT TYPE:",
                                    "DATES & NUMBERS:", "SUMMARY:"
                                ]):
                                    st.markdown(f"**{section}**")
                                elif section.strip():
                                    st.write(section)
                elif st.session_state['current_user']['role'] == 'admin':
                    if st.button("🔍 Analyze", key=f"analyze_status_{doc['id']}"):
                        with st.spinner("Analyzing document..."):
                            if analyze_document(doc):
                                st.success("Analysis completed!")
                                st.rerun()
                            else:
                                st.error("Analysis failed.")
                
                st.divider()
    else:
        st.info("No documents found matching the selected filter")

def show_history_section():
    st.header("Document History 📚")
    
    if st.session_state['history']:
        # Add date range filter
        col1, col2, col3 = st.columns([2, 2, 2])
        with col1:
            start_date = st.date_input("Start date", value=datetime.now() - timedelta(days=30))
        with col2:
            end_date = st.date_input("End date", value=datetime.now())
        with col3:
            if st.session_state['current_user']['role'] == 'admin':
                user_filter = st.selectbox(
                    "Filter by user",
                    ["All Users"] + [user['name'] for user in st.session_state['users'].values()]
                )
        
        # Convert history to DataFrame
        history_df = pd.DataFrame(st.session_state['history'])
        history_df['date'] = pd.to_datetime(history_df['date'])
        
        # Apply filters
        mask = (history_df['date'].dt.date >= start_date) & (history_df['date'].dt.date <= end_date)
        filtered_df = history_df[mask]
        
        if st.session_state['current_user']['role'] == 'admin' and user_filter != "All Users":
            user_email = [email for email, user in st.session_state['users'].items() 
                         if user['name'] == user_filter][0]
            filtered_df = filtered_df[filtered_df['uploaded_by'] == user_email]
        elif st.session_state['current_user']['role'] != 'admin':
            # Regular users can only see their own history
            filtered_df = filtered_df[filtered_df['uploaded_by'] == st.session_state['current_user']['email']]
        
        if not filtered_df.empty:
            # Add user names to the display
            filtered_df['uploaded_by'] = filtered_df['uploaded_by'].apply(
                lambda x: st.session_state['users'][x]['name']
            )
            
            # Display history table
            st.dataframe(
                filtered_df.sort_values('date', ascending=False),
                hide_index=True,
                column_config={
                    "date": st.column_config.DatetimeColumn(
                        "Timestamp",
                        format="D MMM YYYY, HH:mm"
                    ),
                    "id": "Document ID",
                    "name": "Document Name",
                    "status": "Status",
                    "uploaded_by": "Uploaded By"
                }
            )
            
            # Export options
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("Export History"):
                    csv = filtered_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download CSV",
                        csv,
                        "document_history.csv",
                        "text/csv",
                        key='download-csv'
                    )
        else:
            st.info("No documents found in selected date range")
    else:
        st.info("No document history available")

def show_enhanced_analytics():
    if st.session_state['current_user']['role'] != 'admin':
        st.warning("Analytics are only available for administrators.")
        return
        
    st.title("Analytics Dashboard 📊")
    
    if not st.session_state['history']:
        st.info("No data available for analytics yet.")
        return
    
    # Main Analytics Tabs
    tabs = st.tabs([
        "📊 Overview", 
        "👥 User Activity", 
        "⚡ Performance", 
        "📈 Trends",
        "📄 Reports"
    ])
    
    with tabs[0]:  # Overview
        st.header("System Overview")
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        
        df_history = pd.DataFrame(st.session_state['history'])
        with col1:
            st.metric("Total Documents", len(df_history))
            pending = len([d for d in st.session_state['documents'] if d['status'] == 'Pending'])
            st.metric("Pending Documents", pending)
        
        with col2:
            analyzed = len(st.session_state['analyzed_docs'])
            st.metric("Analyzed Documents", analyzed)
            st.metric("Active Users", len(df_history['uploaded_by'].unique()))
        
        with col3:
            approved = len([d for d in st.session_state['documents'] if d['status'] == 'Authorized'])
            if len(df_history) > 0:
                approval_rate = (approved / len(df_history)) * 100
                st.metric("Approval Rate", f"{approval_rate:.1f}%")
            
            today_docs = len(df_history[pd.to_datetime(df_history['date']).dt.date == datetime.now().date()])
            st.metric("Today's Documents", today_docs)
        
        # Status Distribution
        st.subheader("Document Status Distribution")
        status_counts = df_history['status'].apply(lambda x: x.split()[0]).value_counts()
        st.bar_chart(status_counts)
    
    with tabs[1]:  # User Activity
        st.header("User Activity")
        
        df_actions = pd.DataFrame(st.session_state['user_actions'])
        if not df_actions.empty:
            df_actions['timestamp'] = pd.to_datetime(df_actions['timestamp'])
            df_actions['user_name'] = df_actions['user'].apply(
                lambda x: st.session_state['users'][x]['name']
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Activity by User")
                user_activity = df_actions['user_name'].value_counts()
                st.bar_chart(user_activity)
            
            with col2:
                st.subheader("Actions Distribution")
                action_counts = df_actions['action'].value_counts()
                st.bar_chart(action_counts)
            
            # Recent Activity Timeline
            st.subheader("Recent Activity")
            recent = df_actions.sort_values('timestamp', ascending=False).head(10)
            for _, action in recent.iterrows():
                st.text(f"""
🕒 {action['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}
👤 {action['user_name']}
📋 {action['action'].title()}: {action['details']}
""")
    
    with tabs[2]:  # Performance
        st.header("System Performance")
        
        if st.session_state['action_times']:
            col1, col2 = st.columns(2)
            
            with col1:
                time_diffs = [(action - upload).total_seconds() 
                             for upload, action in st.session_state['action_times']]
                
                avg_time = sum(time_diffs) / len(time_diffs)
                max_time = max(time_diffs)
                min_time = min(time_diffs)
                
                st.metric("Average Processing Time", f"{avg_time:.1f} seconds")
                st.metric("Fastest Processing", f"{min_time:.1f} seconds")
                st.metric("Slowest Processing", f"{max_time:.1f} seconds")
            
            with col2:
                st.subheader("Processing Time Distribution")
                time_df = pd.DataFrame(time_diffs, columns=['seconds'])
                st.line_chart(time_df)
    
    with tabs[3]:  # Trends
        st.header("Trend Analysis")
        
        df_history['date'] = pd.to_datetime(df_history['date'])
        
        # Daily volume trend
        st.subheader("Document Volume Trend")
        daily_volume = df_history.groupby(df_history['date'].dt.date).size()
        st.line_chart(daily_volume)
        
        # Status trends
        st.subheader("Status Trends")
        status_by_date = df_history.groupby([
            df_history['date'].dt.date,
            df_history['status'].apply(lambda x: x.split()[0])
        ]).size().unstack(fill_value=0)
        st.line_chart(status_by_date)
        
        # User trends
        st.subheader("User Activity Trends")
        user_by_date = df_history.groupby([
            df_history['date'].dt.date,
            df_history['uploaded_by'].apply(lambda x: st.session_state['users'][x]['name'])
        ]).size().unstack(fill_value=0)
        st.line_chart(user_by_date)
    
    with tabs[4]:  # Reports
        st.header("Custom Reports")
        
        # Report parameters
        col1, col2, col3 = st.columns(3)
        with col1:
            report_start = st.date_input("Start Date", value=datetime.now() - timedelta(days=30))
        with col2:
            report_end = st.date_input("End Date", value=datetime.now())
        with col3:
            selected_user = st.selectbox(
                "Select User",
                ["All Users"] + [user['name'] for user in st.session_state['users'].values()]
            )
        
        # Report metrics selection
        metrics = st.multiselect(
            "Select Metrics to Include",
            ["Document Statistics", "User Activity", "Processing Times", "Status Distribution"],
            default=["Document Statistics"]
        )
        
        if st.button("Generate Report"):
            report_data = {
                "Report Period": f"{report_start} to {report_end}",
                "Generated At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Generated By": st.session_state['current_user']['name'],
                "Metrics": {}
            }
            
            filtered_history = df_history[
                (df_history['date'].dt.date >= report_start) & 
                (df_history['date'].dt.date <= report_end)
            ]
            
            if selected_user != "All Users":
                user_email = [email for email, user in st.session_state['users'].items() 
                            if user['name'] == selected_user][0]
                filtered_history = filtered_history[filtered_history['uploaded_by'] == user_email]
            
            if "Document Statistics" in metrics:
                report_data["Metrics"]["Document Statistics"] = {
                    "Total Documents": len(filtered_history),
                    "Status Distribution": filtered_history['status'].apply(
                        lambda x: x.split()[0]).value_counts().to_dict(),
                    "Analysis Rate": f"{(len(st.session_state['analyzed_docs'])/len(filtered_history)*100):.1f}%"
                }
            
            if "User Activity" in metrics:
                report_data["Metrics"]["User Activity"] = {
                    "Active Users": len(filtered_history['uploaded_by'].unique()),
                    "Documents per User": filtered_history['uploaded_by'].apply(
                        lambda x: st.session_state['users'][x]['name']
                    ).value_counts().to_dict()
                }
            
            # Display and download options
            st.json(report_data)
            
            # Export options
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.download_button(
                    "📥 Download Report",
                    data=json.dumps(report_data, indent=2),
                    file_name=f"analytics_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json"
                ):
                    st.success("Report downloaded successfully!")

def show_navigation():
    st.sidebar.title("Navigation 📱")
    
    nav_options = {
        "Upload": "📤 Upload Documents",
        "Status": "📋 Document Status",
        "History": "📚 Document History",
        "Analytics": "📊 Analytics Dashboard"
    }
    
    # Navigation buttons styled as pills
    st.sidebar.markdown("""
        <style>
        div[data-testid="stRadio"] > div {
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    selected = st.sidebar.radio(
        "Go to",
        list(nav_options.values()),
        label_visibility="collapsed"
    )
    
    # Convert back to original key
    for key, value in nav_options.items():
        if value == selected:
            return key
    return "Upload"

def main():
    if not st.session_state['logged_in']:
        # Login page
        st.title("SignForMe.AI 📝")
        
        # Center the login form
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                st.markdown("### Welcome Back! 👋")
                st.markdown("Please log in to continue")
                
                email = st.text_input("Email", placeholder="Enter your email")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                
                submitted = st.form_submit_button("Login", use_container_width=True)
                
                if submitted:
                    if login_user(email, password):
                        st.session_state['logged_in'] = True
                        log_user_action('login', 'User logged in successfully')
                        st.success("Login successful! Redirecting...")
                        st.rerun()
                    else:
                        st.error("Invalid email or password")
            
            # App info
            with st.expander("ℹ️ About SignForMe.AI"):
                st.markdown("""
                SignForMe.AI is an intelligent document management system that helps you:
                - Upload and analyze documents
                - Track document status
                - Manage approvals
                - Generate insights
                """)
    else:
        # Main application
        header_col1, header_col2 = st.columns([0.7, 0.3])
        with header_col1:
            st.title("SignForMe.AI ✒️")
        with header_col2:
            with st.expander("👤 Profile Menu"):
                st.write(f"Welcome, {st.session_state['current_user']['name']}!")
                st.write(f"Role: {st.session_state['current_user']['role'].title()}")
                st.divider()
                
                if st.session_state['current_user']['role'] == 'admin':
                    if st.button("📊 Dashboard"):
                        st.session_state['selected_view'] = 'Analytics'
                
                if st.button("ℹ️ About"):
                    st.info("""SignForMe.AI v6.0
                    Developed by Kalinov Jim
                    
                    A smart document management system with AI-powered analysis.
                    """)
                
                if st.button("🚪 Logout"):
                    log_user_action('logout', 'User logged out')
                    st.session_state['logged_in'] = False
                    st.rerun()
        
        # Sidebar navigation
        view = show_navigation()
        
        # Main content container
        with st.container():
            if view == "Upload":
                show_upload_section()
            elif view == "Status":
                show_status_section()
            elif view == "History":
                show_history_section()
            elif view == "Analytics":
                show_enhanced_analytics()
        
        # Footer
        st.sidebar.divider()
        st.sidebar.caption("""
        © 2024 SignForMe.AI
        Version 6.0
        """)

if __name__ == "__main__":
    main()

