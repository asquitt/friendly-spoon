# Jupyter Notebook Environment for LLM Feature Store
# This provides an interactive environment for exploring features and testing

FROM jupyter/scipy-notebook:python-3.11

# Install additional dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Set working directory
WORKDIR /home/jovyan/work

# Expose Jupyter port
EXPOSE 8888
