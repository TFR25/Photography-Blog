import os
from datetime import datetime, date

from flask import Flask, redirect, url_for, flash, abort
from flask import render_template
from flask_avatars import Avatars
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_login import UserMixin, LoginManager, login_user, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, Text, String
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase, relationship
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm

now = datetime.now()
current_year = now.year

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///./tfr_photography_blog.db'
db = SQLAlchemy()
db.init_app(app)
Bootstrap5(app)
ckeditor = CKEditor(app)
avatars = Avatars(app)


class Base(DeclarativeBase):
    pass


# Create a User table for all your registered users
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(100))

    # This will act like a List of Posts objects attached to each User.
    # The "author" refers to the author property in the BlogPost class.
    posts = relationship("Posts", back_populates="author")

    # *******Add parent relationship*******#
    # "comment_author" refers to the comment_author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")


class Posts(db.Model):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    img_url: Mapped[str] = mapped_column(String(250), nullable=False)
    title: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    subtitle: Mapped[str] = mapped_column(String(250), nullable=False)
    date: Mapped[str] = mapped_column(String(250), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Child Relationship #
    # Create Foreign Key, "users.id" the users refers to the tablename of User.
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    # Create reference to the User object. The "posts" refers to the posts property in the User class.
    author = relationship("User", back_populates="posts")

    # Parent Relationship #
    comments = relationship("Comment", back_populates="parent_post")

# Create comment table
class Comment(db.Model):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")

    # ***************Child Relationship*************#
    post_id: Mapped[str] = mapped_column(Integer, db.ForeignKey("posts.id"))
    parent_post = relationship("Posts", back_populates="comments")
    text: Mapped[str] = mapped_column(Text, nullable=False)


login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


#Create admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function


@app.route('/')
def index():
    result = db.session.execute(db.select(Posts))
    recent = result.scalars().all()
    return render_template('index.html', recent_post=recent, year=current_year)


@app.route('/about')
def about():
    return render_template('about.html', year=current_year)


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    api = os.getenv('SBFORM')
    return render_template('contact.html', api=api, year=current_year)


@app.route("/footer")
def footer():
    return render_template('footer.html', year=current_year)


@app.route('/get_all_blog_posts')
def get_all_blog_posts():
    result = db.session.execute(db.select(Posts).order_by(Posts.id.desc()))
    all_posts = result.scalars().all()

    return render_template('blogPosts.html', all_posts=all_posts, year=current_year)


@app.route('/requested_post/<int:post_id>', methods=['GET', 'POST'])
def show_post(post_id):
    requested_post = db.get_or_404(Posts, post_id)
    # Add the CommentForm to the route
    form = CommentForm()
    # Only allow logged-in users to comment on posts
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))

        new_comment = Comment(
            text=form.comment_text.data,
            comment_author=current_user,
            parent_post=requested_post
        )
        db.session.add(new_comment)
        db.session.commit()
    return render_template('requested_post.html', post=requested_post, form=form, current_user=current_user, year=current_year)


@app.route('/new-post', methods=['GET', 'POST'])
@login_required
def add_new_post():
    # Only allow admin to create posts
    form = CreatePostForm()
    if form.validate_on_submit():

        # Check if user email is already present in the database.
        result = db.session.execute(db.select(Posts).where(Posts.title == form.title.data))
        title = result.scalar()
        if title:
            # User already exists
            flash("This title is already taken. Please create a unique title.")
            return render_template('createPost.html', form=form, year=current_year)
        else:
            new_post = Posts(
                img_url=form.img_url.data,
                title=form.title.data,
                subtitle=form.subtitle.data,
                date=date.today().strftime('%B %d, %Y'),
                body=form.body.data,
                author=current_user
            )
            db.session.add(new_post)
            db.session.commit()
        return redirect(url_for('get_all_blog_posts'))
    return render_template('createPost.html', form=form, year=current_year)


# Editing an existing post
@app.route("/edit_post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    # Only allow admin to create and edit posts
    requested_post = db.get_or_404(Posts, post_id)
    edit_form = CreatePostForm(
        img_url=requested_post.img_url,
        title=requested_post.title,
        subtitle=requested_post.subtitle,
        body=requested_post.body,
        author=current_user,
    )
    if edit_form.validate_on_submit():
        requested_post.img_url = edit_form.img_url.data
        requested_post.title = edit_form.title.data
        requested_post.subtitle = edit_form.subtitle.data
        requested_post.body = edit_form.body.data
        requested_post.author = current_user

        db.session.commit()
        return redirect(url_for("show_post", post_id=requested_post.id))
    return render_template("createPost.html", form=edit_form, is_edit=True, current_user=current_user)


@app.route("/delete_post/<int:post_id>")
@admin_only
@login_required
def delete_post(post_id):
    post_to_delete = db.get_or_404(Posts, post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for("get_all_blog_posts"))


@app.route("/delete_comment/<int:id>")
@admin_only
@login_required
def delete_comment(id):
    comment_to_delete = db.get_or_404(Comment, id)
    db.session.delete(comment_to_delete)
    db.session.commit()
    return redirect(url_for("get_all_blog_posts"))


# Register new users into the User database
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Check if user email is already present in the database.
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_blog_posts"))
    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('get_all_blog_posts'))
    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_blog_posts'))


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
