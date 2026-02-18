import sys
from os.path import dirname, abspath
sys.path.insert(0, dirname(dirname(abspath(__file__))))



from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import  Mapped, mapped_column, relationship

try: from .database import Base
except ImportError: from database import Base
    

from datetime import date

class User(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(100), nullable=False)
    registered: Mapped[date] = mapped_column()
    agents: Mapped[list['Agent']] = relationship(back_populates='user')

    def __str__(self):
        return (f'''
                id={self.id} 
                name={self.name}
                registered={self.registered}
                ''')

    def __repr__(self):
        return str(self)

class Agent(Base):
    id: Mapped[int] = mapped_column(primary_key=True)

    user: Mapped['User'] = relationship(back_populates='agents')
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    
agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(100), nullable=False)
    

    registered: Mapped[date] = mapped_column()

    def __str__(self):
        return (f'''
                id={self.id} 
                agent_id={self.agent_id}
                registered={self.registered}
                ''')

    def __repr__(self):
        return str(self)









