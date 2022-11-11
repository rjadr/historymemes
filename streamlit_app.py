from autogluon.multimodal import MultiModalPredictor
import datasets
import pandas as pd
from PIL import Image
import subprocess
import streamlit as st


# Set Huggingface token
token = st.secrets["token"]
left_of_pipe = subprocess.Popen(["echo", token], stdout=subprocess.PIPE)
right_of_pipe = subprocess.run(['huggingface-cli', 'login'], stdin=left_of_pipe.stdout,
                               stdout=subprocess.PIPE).stdout.decode('utf-8')


# Load the dataset
@st.cache(allow_output_mutation=True)
def load_data(dataset_name):
    dataset = datasets.load_dataset(dataset_name, use_auth_token=True)
    return dataset

with st.spinner('Loading dataset. This could take a while...'):
    dataset = load_data('rjadr/HistoryMemes')
    dataset['train'].add_faiss_index(column="txt_embs")
    dataset['train'].add_faiss_index(column="img_embs")

# Load CLIP model
@st.cache(allow_output_mutation=True)
def get_model(model_name):
    """
    Load the CLIP model

    Parameters:
    model_name (str): Name of the model to load

    Returns:
    model (autogluon.multimodal.MultiModalPredictor): autogluon MultiModalPredictor
    """
    model = MultiModalPredictor(hyperparameters={"model.names": [model_name]}, problem_type="zero_shot")
    return model


predictor = get_model('clip')


@st.cache
def get_image_embs(uploaded_file):
    """
    Get image embeddings

    Parameters:
    uploaded_file (UploadedFile): Uploaded image file

    Returns:
    img_emb (np.array): Image embeddings
    """
    image = Image.open(uploaded_file)
    img_emb = predictor.extract_embedding({"image": [image]})
    return img_emb['image'][0]


@st.cache
def get_text_embs(text):
    """
    Get text embeddings

    Parameters:
    text (str): Text to encode

    Returns:
    text_emb (np.array): Text embeddings
    """
    txt_emb = predictor.extract_embedding({"text": [text]})
    return txt_emb['text'][0]

    
# Header
st.title('/r/HistoryMemes Multimodal Search')
st.write(
    'This is an example of multimodal retrieval on multimodal embeddings on a subset of 20,000 memes from /r/HistoryMemes. The embeddings are generated by the [CLIP](https://huggingface.co/sentence-transformers/clip-ViT-B-32) model. The dataset is stored on the [Hugging Face Hub](https://huggingface.co/datasets/rjadr/HistoryMemes). (private dataset). The code for this example is available on [GitHub](https://github.com/rjadr/historymemes).')


# Sidebar
st.sidebar.header('Search')
st.sidebar.write('Search for a meme by text or image.')
st.sidebar.write('First, select the type of search you want to perform.')
search_type = st.sidebar.selectbox('Search Type',
                                   ['', 'Text to text', 'Text to Image', 'Image to Image', 'Image to Text'],
                                   format_func=lambda x: 'Select search type' if x == '' else x)
k = st.sidebar.slider('Number of results', 1, 10, 5)

scores = None
samples = None

if search_type == 'Text to text':
    st.sidebar.write('**Enter a text query:**')
    query = st.sidebar.text_input('Query')
    if query != '':
        with st.spinner('Processing query...'):
            scores, samples = dataset['train'].get_nearest_examples('txt_embs', get_text_embs(query), k=k)

elif search_type == 'Text to Image':
    st.sidebar.write('**Enter a text query:**')
    query = st.sidebar.text_input('Query')
    if query != '':
        with st.spinner('Processing query...'):
            scores, samples = dataset['train'].get_nearest_examples('img_embs', get_text_embs(query), k=k)

elif search_type == 'Image to Image':
    st.sidebar.write('**Upload an image:**')
    query = st.sidebar.file_uploader('Query')
    if query is not None:
        with st.spinner('Processing query...'):
            scores, samples = dataset['train'].get_nearest_examples('img_embs', get_image_embs(query), k=k)

elif search_type == 'Image to Text':
    st.sidebar.write('**Upload an image:**')
    query = st.sidebar.file_uploader('Query')
    if query is not None:
        with st.spinner('Processing query...'):
            scores, samples = dataset['train'].get_nearest_examples('txt_embs', get_image_embs(query), k=k)


if scores is not None:
    samples_df = pd.DataFrame.from_dict(samples)
    samples_df["scores"] = scores
    samples_df["scores"] = (1 - (samples_df["scores"] - samples_df["scores"].min()) / (
        samples_df["scores"].max() - samples_df["scores"].min())) * 100
    samples_df["scores"] = samples_df["scores"].astype(int)
    samples_df.reset_index(inplace=True, drop=True)
    
    st.write('## Results')
    for index, sample in samples_df.iterrows():
        st.write(f'### {index + 1}: {sample["title"]}')
        st.write(f'**Score:** {sample["scores"]} %')
        st.write(
            f'**Url:** [{"https://www.reddit.com/" + sample["permalink"]}]({"https://www.reddit.com/" + sample["permalink"]})')
        st.image(sample['image'])
        st.markdown("""<hr style="height:10px;border:none;color:#333;background-color:#333;" /> """,
                    unsafe_allow_html=True)
