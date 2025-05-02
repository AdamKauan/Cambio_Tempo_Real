from flask import Flask, render_template, request
import requests
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from datetime import datetime, timezone
import matplotlib.pyplot as plt
import io
import base64


app = Flask(__name__)

# Conectando ao banco
# Configuração do banco de dados
app.config['SQLALCHEMY_DATABASE_URI'] = 'mssql+pyodbc://DMM\\SQLMATIAS/CambioMoeda?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa o SQLAlchemy
db = SQLAlchemy(app)

# Armazenamento de conversões
class Conversao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    id_usuario = db.Column(db.Integer, nullable=True)
    moeda_origem = db.Column(db.String(3), nullable=False)
    moeda_destino = db.Column(db.String(3), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    resultado = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<Conversao {self.moeda_origem} para {self.moeda_destino}>"

# Conectando API
API_URL = "https://v6.exchangerate-api.com/v6/a540b65965f01b39aca03b55/latest/"

@app.route("/testar_conexao")
def testar_conexao():
    try:
        db.session.execute(text('SELECT 1'))
        return "Conexão bem-sucedida ao banco de dados!"
    except Exception as e:
        return f"Erro na conexão com o banco de dados: {str(e)}"


@app.route("/", methods=["GET", "POST"])
def index():
    resultado = None
    if request.method == "POST":
        moeda_origem = request.form["moeda_origem"]
        moeda_destino = request.form["moeda_destino"]
        valor = float(request.form["valor"])
        
        # Consulta de câmbio
        resposta = requests.get(f"{API_URL}{moeda_origem}")
        dados = resposta.json()
        
        if resposta.status_code == 200 and moeda_destino in dados["conversion_rates"]:
            taxa_cambio = dados["conversion_rates"][moeda_destino]
            resultado = round(valor * taxa_cambio, 2)
            
            # Armazenar conversão no banco
            nova_conversao = Conversao(
                moeda_origem=moeda_origem,
                moeda_destino=moeda_destino,
                valor=valor,
                resultado=resultado
            )
            db.session.add(nova_conversao)
            db.session.commit()
        else:
            resultado = "Erro na conversão"
    return render_template("index.html", resultado=resultado)

@app.route("/estatisticas")
def estatisticas():
    try:
        # Consultar o banco de dados para obter as estatísticas das conversões
        conversoes_por_moeda = db.session.query(
            Conversao.moeda_destino, db.func.count(Conversao.id).label('total_conversoes')
        ).group_by(Conversao.moeda_destino).all()
        
        # Preparar os dados para os gráficos
        moedas = [item.moeda_destino for item in conversoes_por_moeda]
        total_conversoes = [item.total_conversoes for item in conversoes_por_moeda]
        
        # Criar o gráfico de barras
        fig, ax = plt.subplots(figsize=(10, 7))  
        ax.bar(moedas, total_conversoes, color=plt.cm.Paired.colors)
        ax.set_xlabel('Moedas')
        ax.set_ylabel('Nº de Conversões')
        ax.set_title('Número de Conversões por Moeda', pad = 30)
        
        # Salvar o gráfico em uma imagem em memória
        img_bar = io.BytesIO()
        plt.savefig(img_bar, format='png')
        img_bar.seek(0)
        grafico_bar_base64 = base64.b64encode(img_bar.getvalue()).decode('utf8')
        
        # Criar o gráfico de pizza
        fig_pie, ax_pie = plt.subplots(figsize=(10, 8))
        ax_pie.pie(total_conversoes, labels=moedas, autopct='%1.1f%%', startangle=110, colors=plt.cm.Paired.colors)
        ax_pie.set_title('Percentual das Conversões por Moeda', pad=-40)
        
        # Salvar o gráfico de pizza em uma imagem em memória
        img_pie = io.BytesIO()
        plt.savefig(img_pie, format='png')
        img_pie.seek(0)
        grafico_pie_base64 = base64.b64encode(img_pie.getvalue()).decode('utf8')
        
        # Passar moedas e total_conversoes diretamente para o template
        dados_conversao = zip(moedas, total_conversoes)
        
        # Retornar os gráficos e exibir na página HTML
        return render_template('estatisticas.html', 
                               grafico_bar=grafico_bar_base64, 
                               grafico_pie=grafico_pie_base64,
                               dados_conversao=dados_conversao)
    except Exception as e:
        return f"Ocorreu um erro: {str(e)}"

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Cria tabelas no banco
    app.run(debug=True, use_reloader=True)
