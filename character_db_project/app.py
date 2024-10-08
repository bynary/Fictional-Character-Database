from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.hybrid import hybrid_property
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # Use the 'Agg' backend which doesn't require a GUI
import matplotlib.pyplot as plt
import networkx as nx
import datetime
from scipy import interpolate
import numpy as np




app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///characters.db'
app.config['SECRET_KEY'] = 'your_secret_key'  # needed for flashing messages
db = SQLAlchemy(app)

class Character(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    arcs = db.relationship('CharacterArc', backref='character', lazy=True)
    relationships_from = db.relationship('Relationship', foreign_keys='Relationship.character_from_id', backref='character_from', lazy=True)
    relationships_to = db.relationship('Relationship', foreign_keys='Relationship.character_to_id', backref='character_to', lazy=True)

class CharacterArc(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)
    act1_self_esteem = db.Column(db.Float)
    act1_social_reputation = db.Column(db.Float)
    act2_self_esteem = db.Column(db.Float)
    act2_social_reputation = db.Column(db.Float)
    act3_self_esteem = db.Column(db.Float)
    act3_social_reputation = db.Column(db.Float)

    @hybrid_property
    def act1_psychological_index(self):
        return self.act1_self_esteem - self.act1_social_reputation

    @hybrid_property
    def act2_psychological_index(self):
        return self.act2_self_esteem - self.act2_social_reputation

    @hybrid_property
    def act3_psychological_index(self):
        return self.act3_self_esteem - self.act3_social_reputation

class Relationship(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    character_from_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)
    character_to_id = db.Column(db.Integer, db.ForeignKey('character.id'), nullable=False)
    relationship_type = db.Column(db.String(50), nullable=False)
    intensity = db.Column(db.Integer, nullable=False)  # Scale from 1 to 10

@app.route('/')
def index():
    characters = Character.query.all()
    return render_template('index.html', characters=characters)

@app.route('/add', methods=['POST'])
def add_character():
    name = request.form['name']
    description = request.form['description']
    new_character = Character(name=name, description=description)
    db.session.add(new_character)
    db.session.commit()
    flash('Character added successfully!')
    return redirect(url_for('index'))

@app.route('/character/<int:id>')
def character_detail(id):
    character = Character.query.get_or_404(id)
    arc = CharacterArc.query.filter_by(character_id=id).first()
    relationships = Relationship.query.filter((Relationship.character_from_id == id) | (Relationship.character_to_id == id)).all()
    characters = Character.query.all()
    return render_template('character_detail.html', character=character, arc=arc, relationships=relationships, characters=characters)

@app.route('/character/<int:id>/edit', methods=['GET', 'POST'])
def edit_character(id):
    character = Character.query.get_or_404(id)
    if request.method == 'POST':
        character.name = request.form['name']
        character.description = request.form['description']
        db.session.commit()
        flash('Character updated successfully!')
        return redirect(url_for('character_detail', id=character.id))
    return render_template('edit_character.html', character=character)

@app.route('/character/<int:id>/delete', methods=['POST'])
def delete_character(id):
    character = Character.query.get_or_404(id)
    db.session.delete(character)
    db.session.commit()
    flash('Character deleted successfully!')
    return redirect(url_for('index'))

@app.route('/character/<int:id>/add_arc', methods=['POST'])
def add_character_arc(id):
    character = Character.query.get_or_404(id)
    existing_arc = CharacterArc.query.filter_by(character_id=id).first()
    if existing_arc:
        flash('Character arc already exists. Use edit function to modify.')
        return redirect(url_for('character_detail', id=id))
    
    new_arc = CharacterArc(
        character_id=id,
        act1_self_esteem=float(request.form['act1_self_esteem']),
        act1_social_reputation=float(request.form['act1_social_reputation']),
        act2_self_esteem=float(request.form['act2_self_esteem']),
        act2_social_reputation=float(request.form['act2_social_reputation']),
        act3_self_esteem=float(request.form['act3_self_esteem']),
        act3_social_reputation=float(request.form['act3_social_reputation'])
    )
    db.session.add(new_arc)
    db.session.commit()
    flash('Character arc added successfully!')
    return redirect(url_for('character_detail', id=id))

@app.route('/character/<int:id>/edit_arc', methods=['POST'])
def edit_character_arc(id):
    character = Character.query.get_or_404(id)
    arc = CharacterArc.query.filter_by(character_id=id).first()
    if arc:
        arc.act1_self_esteem = float(request.form['act1_self_esteem'])
        arc.act1_social_reputation = float(request.form['act1_social_reputation'])
        arc.act2_self_esteem = float(request.form['act2_self_esteem'])
        arc.act2_social_reputation = float(request.form['act2_social_reputation'])
        arc.act3_self_esteem = float(request.form['act3_self_esteem'])
        arc.act3_social_reputation = float(request.form['act3_social_reputation'])
        db.session.commit()
        flash('Character arc updated successfully!')
    else:
        flash('Character arc not found!')
    return redirect(url_for('character_detail', id=id))

@app.route('/character/<int:id>/arc_data')
def character_arc_data(id):
    character = Character.query.get_or_404(id)
    arc = CharacterArc.query.filter_by(character_id=id).first()
    if arc:
        x = [0, 1, 2]
        y = [arc.act1_psychological_index, arc.act2_psychological_index, arc.act3_psychological_index]
        x_smooth, y_smooth = create_curve(x, y)
        data = {
            'labels': ['Act 1', 'Act 2', 'Act 3'],
            'psychological_index': y,
            'x_smooth': x_smooth.tolist(),
            'y_smooth': y_smooth.tolist()
        }
        return jsonify(data)
    return jsonify({'error': 'No arc data available'})

@app.route('/character/<int:id>/add_relationship', methods=['POST'])
def add_relationship(id):
    character_from = Character.query.get_or_404(id)
    character_to_id = request.form['character_to_id']
    relationship_type = request.form['relationship_type']
    intensity = int(request.form['intensity'])

    new_relationship = Relationship(
        character_from_id=id,
        character_to_id=character_to_id,
        relationship_type=relationship_type,
        intensity=intensity
    )
    db.session.add(new_relationship)
    db.session.commit()
    flash('Relationship added successfully!')
    return redirect(url_for('character_detail', id=id))

@app.route('/character/<int:id>/edit_relationship/<int:relationship_id>', methods=['POST'])
def edit_relationship(id, relationship_id):
    relationship = Relationship.query.get_or_404(relationship_id)
    relationship.relationship_type = request.form['relationship_type']
    relationship.intensity = int(request.form['intensity'])
    db.session.commit()
    flash('Relationship updated successfully!')
    return redirect(url_for('character_detail', id=id))

@app.route('/character/<int:id>/relationships')
def character_relationships(id):
    character = Character.query.get_or_404(id)
    relationships = Relationship.query.filter((Relationship.character_from_id == id) | (Relationship.character_to_id == id)).all()
    
    nodes = [{"id": character.id, "name": character.name}]
    links = []
    
    for rel in relationships:
        other_character = rel.character_to if rel.character_from_id == id else rel.character_from
        nodes.append({"id": other_character.id, "name": other_character.name})
        links.append({
            "source": rel.character_from_id,
            "target": rel.character_to_id,
            "intensity": rel.intensity,
            "type": rel.relationship_type
        })
    
    return jsonify({"nodes": nodes, "links": links})

@app.route('/relationships')
def relationships():
    return render_template('relationships.html')

@app.route('/all_relationships')
def all_relationships():
    relationships = Relationship.query.all()
    characters = Character.query.all()
    
    nodes = [{"id": character.id, "name": character.name} for character in characters]
    links = []
    
    for rel in relationships:
        links.append({
            "source": rel.character_from_id,
            "target": rel.character_to_id,
            "intensity": rel.intensity,
            "type": rel.relationship_type
        })
    
    return jsonify({"nodes": nodes, "links": links})

@app.route('/compare_characters')
def compare_characters():
    characters = Character.query.all()
    return render_template('compare_characters.html', characters=characters)

@app.route('/compare_characters_data', methods=['POST'])
def compare_characters_data():
    character_ids = request.json['character_ids']
    data = []
    for id in character_ids:
        character = Character.query.get(id)
        arc = CharacterArc.query.filter_by(character_id=id).first()
        if character and arc:
            x = [0, 1, 2]
            y = [arc.act1_psychological_index, arc.act2_psychological_index, arc.act3_psychological_index]
            x_smooth, y_smooth = create_curve(x, y)
            data.append({
                'name': character.name,
                'psychological_index': y,
                'x_smooth': x_smooth.tolist(),
                'y_smooth': y_smooth.tolist()
            })
    return jsonify({
        'labels': ['Act 1', 'Act 2', 'Act 3'],
        'datasets': data
    })

@app.route('/how_to_use')
def how_to_use():
    return render_template('how_to_use.html')

@app.route('/generate_pdf', methods=['GET', 'POST'])
def generate_pdf():
    if request.method == 'POST':
        author_name = request.form['author_name']
        work_title = request.form['work_title']
        return generate_character_bible_pdf(author_name, work_title)
    return render_template('generate_pdf.html')

def generate_character_bible_pdf(author_name, work_title):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CenterTitle', parent=styles['Title'], alignment=1))
    
    Story = []
    
    # Front matter
    Story.append(Paragraph(work_title, styles['CenterTitle']))
    Story.append(Spacer(1, 12))
    Story.append(Paragraph(author_name, styles['CenterTitle']))
    Story.append(Spacer(1, 36))
    Story.append(Paragraph("Character Bible", styles['CenterTitle']))
    Story.append(Spacer(1, 36))
    current_year = datetime.datetime.now().year
    Story.append(Paragraph(f"Copyright, {author_name}, {current_year}", styles['CenterTitle']))
    Story.append(PageBreak())
    
    # Characters Section
    characters = Character.query.order_by(Character.name).all()
    for character in characters:
        Story.append(Paragraph(character.name, styles['Heading1']))
        Story.append(Paragraph(character.description, styles['Normal']))
        Story.append(Spacer(1, 12))
        
        # Character Arc
        Story.append(Paragraph("Character Arc", styles['Heading2']))
        arc = CharacterArc.query.filter_by(character_id=character.id).first()
        if arc:
            x = [0, 1, 2]
            y = [arc.act1_psychological_index, arc.act2_psychological_index, arc.act3_psychological_index]
            x_smooth, y_smooth = create_curve(x, y)
            
            plt.figure(figsize=(6, 4))
            plt.plot(x_smooth, y_smooth, '-')
            plt.plot(x, y, 'o')
            plt.title(f"{character.name}'s Psychological Index")
            plt.xlabel("Story Acts")
            plt.ylabel("Psychological Index")
            plt.xticks([0, 1, 2], ['Act 1', 'Act 2', 'Act 3'])
            img_buffer = BytesIO()
            plt.savefig(img_buffer, format='png')
            plt.close()
            img_buffer.seek(0)
            img = Image(img_buffer)
            img.drawHeight = 3*inch
            img.drawWidth = 4*inch
            Story.append(img)
        
        Story.append(Spacer(1, 12))
        
        # Relationships
        Story.append(Paragraph("Relationships", styles['Heading2']))
        relationships = Relationship.query.filter((Relationship.character_from_id == character.id) | (Relationship.character_to_id == character.id)).all()
        G = nx.Graph()
        for rel in relationships:
            other_character = rel.character_to if rel.character_from_id == character.id else rel.character_from
            G.add_edge(character.name, other_character.name, weight=rel.intensity)
        
        plt.figure(figsize=(6, 4))
        pos = nx.spring_layout(G)
        nx.draw(G, pos, with_labels=True, node_color='lightblue', node_size=500, font_size=8)
        edge_labels = nx.get_edge_attributes(G, 'weight')
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels)
        
        network_buffer = BytesIO()
        plt.savefig(network_buffer, format='png')
        plt.close()
        network_buffer.seek(0)
        network_img = Image(network_buffer)
        network_img.drawHeight = 3*inch
        network_img.drawWidth = 4*inch
        Story.append(network_img)
        
        Story.append(PageBreak())
    
    # Build the PDF
    doc.build(Story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    
    buffer.seek(0)
    return send_file(buffer, 
                     download_name='character_bible.pdf',
                     as_attachment=True, 
                     mimetype='application/pdf')





def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont('Times-Roman', 10)
    page_num = canvas.getPageNumber()
    text = f"Page {page_num}"
    canvas.drawRightString(7.5*inch, 0.5*inch, text)
    canvas.restoreState()


def create_curve(x, y):
    t = np.arange(len(x))
    t_new = np.linspace(t.min(), t.max(), 100)
    spl = interpolate.make_interp_spline(t, y, k=2)  # type: BSpline
    y_smooth = spl(t_new)
    return t_new, y_smooth





if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5003)
