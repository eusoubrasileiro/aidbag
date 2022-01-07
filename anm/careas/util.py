import datetime
import sys
from dateutil.relativedelta import relativedelta

def ContaPrazo(dou_dia=21, dou_mes=12, dou_ano=1993, prazo_dias=30, prazo_meses=0):
    """
    Contagem de Prazo
    PARECER/PROGE Nº 173, de 2008
    item 24. (a,b,c) Conclusão definem a regra

    * dataDOU: tuple(dia, mes, ano)
        data da publicacao em DOU
    """
    start = datetime.datetime(dou_ano, dou_mes, dou_dia)
    # **Monday == 0 ... Friday=4, Saturday=5, Sunday == 6**
    time = relativedelta(year=0, days=prazo_dias, months=prazo_meses) # prazo
    WeekDay= dict(zip(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], list(range(7))))
    WeekDayr =  {v:k for k,v in WeekDay.items()} # reverse_dictionary
    # (b) (c)
    # o prazo começa a contar no dia seguinte ao da publicaçao
    # desde que exista expediente nesse dia (ou seja dia útil)
    # caso nao seja a contagem começa a contar do próximo dia com expediente (ou dia útil)
    print('Publicado    :', start.strftime(r"%d/%m/%y"), WeekDayr[start.weekday()], file=sys.stdout)
    if start.weekday()+1 == WeekDay['Saturday']: # contagem começaria no sábado
        start = start + relativedelta(days=2) # ínicio é domingo para prazo começar na segunda
    print('Ínicio       :', start.strftime(r"%d/%m/%y"), WeekDayr[start.weekday()], file=sys.stdout)
    # isso deve-se ao fato da data final ser incluída na contagem
    # e.g dia 25/10/2010 sexta-feira publicado - prazo 2 dias
    # contagem inicia no dia seguinte, entretanto, esse é sábado logo
    # a data de início para a soma pode ser deslocada para (+2)
    # 27/10/2010 domingo, e soma-se 2 dias para chegar a data final (incluída)
    # 30/10/2010 terça-feira
    deadline = start + time
    print('Prazo final  :', deadline.strftime(r"%d/%m/%y"), WeekDayr[deadline.weekday()], file=sys.stdout)
    # último dia do prazo DEVE ser dia de expediente (ou útil)
    if deadline.weekday() == WeekDay['Saturday']:
        deadline += relativedelta(days=2)
    if deadline.weekday() == WeekDay['Sunday']:
        deadline += relativedelta(days=1)
    print('Prazo final  :', deadline.strftime(r"%d/%m/%y"),  WeekDayr[deadline.weekday()], file=sys.stdout)
