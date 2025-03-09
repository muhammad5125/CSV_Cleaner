import streamlit as st 
import pandas as pd
import csv
from io import BytesIO


# Load the csv file, check encoding and delimiter
def read_csv(uploaded_file):
    if uploaded_file is None:
        st.error("No file uploaded.")
        return None

    if uploaded_file.size == 0:
        st.error("The uploaded file is empty.")
        return None

    uploaded_file.seek(0)  # Reset file pointer
    
    encodings = ["utf-8", "latin1", "ISO-8859-1"]
    for encoding in encodings:
        try:
            df = pd.read_csv(uploaded_file, encoding=encoding, sep=',')
            if df.shape[1] == 0:
                st.error("No valid columns found in the uploaded CSV.")
                return None

            if df.shape[1] == 1:
                uploaded_file.seek(0)
                sample = uploaded_file.read(2048).decode(encoding)
                detected_delimiter = csv.Sniffer().sniff(sample).delimiter
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding=encoding, sep=detected_delimiter)

            return df
        except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError):
            continue

    st.error("Error: Unable to read the file. Ensure it's a valid CSV.")
    return None

# Standardize the column names
def standard_col_names(df):
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    df = df.loc[:, ~df.columns.duplicated()]  # Remove duplicate columns
    return df

# Remove the missing values
def missing_vals(df , act):
    if act == "Add Value":
        for col in df.select_dtypes(include=['number']).columns:
            skewness = df[col].dropna().skew()
            df[col].fillna(df[col].mean() if abs(skewness) < 1 else df[col].median(), inplace=True)
        for col in df.select_dtypes(include=['object']).columns:
            if not df[col].mode().empty:
                df[col].fillna(df[col].mode()[0], inplace=True)
    else:
         df.dropna(inplace=True)
    return df

# Remove duplicates
def remove_duplicates(df):
    df.drop_duplicates(inplace=True)
    return df

# Convert object columns to categorical
def convert_categories(df):
    categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
    for col in categorical_cols:
        df[col] = df[col].astype("category")
    return df


# Handle outliers
def handle_outliers(df, action):
    if action == "Remove":
        for col in df.select_dtypes(include=['number']).columns:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            df = df[(df[col] >= lower_bound) & (df[col] <= upper_bound)]

    elif action == "Replace":
        for col in df.select_dtypes(include=['number']).columns:
            skewness = df[col].dropna().skew()
            if abs(skewness) < 1 and abs(skewness) > -1 :
                mean, std = df[col].mean(), df[col].std()
                z_score = (df[col] - mean) / std
                df.loc[(z_score > 3) | (z_score < -3), col] = mean  # Replace outliers with mean
            else:
                q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
                iqr = q3 - q1
                outliers = (df[col] < (q1 - 1.5 * iqr)) | (df[col] > (q3 + 1.5 * iqr))
                df.loc[outliers, col] = df[col].median()  # Replace outliers with median
    return df

# Convert date columns
def convert_date_cols(df, date_columns):
    if not isinstance(date_columns, list):  # Ensure it's a list
        st.warning("⚠ No date columns specified. Skipping date conversion.")
        return df

    for col in date_columns:
        if col not in df.columns:
            continue
        try:
            df[col] = pd.to_datetime(df[col], errors='coerce')
        except Exception as e:
            st.error(f"🚨 Error converting {col} to datetime: {e}")
    
    return df


# Save cleaned data to buffer
def save_to_buffer(df):
    try:
        output = BytesIO()
        df.to_csv(output, index=False)
        return output.getvalue()
    except Exception as e:
        st.error(f"Error saving cleaned data: {e}")
        return None

# Cleaning Process
def cleaning_process(df, missing_method , outlier_action , date_columns):
    if df is None or df.empty:
        st.error("Uploaded file is empty. Please upload a valid CSV.")
        return None
    df = standard_col_names(df)
    df = remove_duplicates(df)
    df = missing_vals(df , missing_method)
    df = convert_categories(df)
    df = handle_outliers(df , outlier_action)
    df = convert_date_cols(df , date_columns)
    return df

# Streamlit UI
st.set_page_config(page_title="CSV Data Cleaning Tool", page_icon="🧹", layout="wide")
st.title("🧹 CSV Data Cleaning Tool")
st.markdown("""
### 📌 Upload a CSV file, and the tool will clean the data:
- ✅ Remove missing values (Customizable)
- ✅ Handle outliers (Remove or Replace)
- ✅ Standardize column names
- ✅ Remove duplicates
- ✅ Convert categories and dates (User selection)
""")

st.sidebar.header("Upload Your File")
uploaded_file = st.sidebar.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    df = read_csv(uploaded_file)
    if df is not None:
        st.subheader("📊 Original Data Preview")
        st.dataframe(df.head(), use_container_width=True)

        missing_method = st.sidebar.selectbox("Missing Value Handling", ["Add Value", "Drop"])
        outlier_action = st.sidebar.selectbox("Outlier Handling", ["Remove", "Replace", "Keep"])
        date_columns = st.sidebar.multiselect("Select Date Columns", df.columns.tolist() if df is not None else [])


        if st.sidebar.button("Clean Data"):
            with st.spinner("🔄 Processing..."):
                cleaned_df = cleaning_process(df, missing_method, outlier_action, date_columns)  # Pass df, not uploaded_file
                if cleaned_df is not None:
                    st.subheader("✨ Cleaned Data Preview")
                    st.dataframe(cleaned_df.head(), use_container_width=True)
                    cleaned_file = save_to_buffer(cleaned_df)
                    if cleaned_file:
                        st.download_button(
                            label="⬇️ Download Cleaned CSV",
                            data=cleaned_file,
                            file_name="cleaned_data.csv",
                            mime="text/csv",
                            help="Click to download the cleaned dataset"
                        )
                    else:
                        st.error("🚨 Error generating cleaned file.")
