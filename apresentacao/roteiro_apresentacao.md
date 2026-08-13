# Roteiro executivo — Receita Certa

Tempo sugerido: 12 a 15 minutos.

## 1. Capa — 30 segundos

“O Receita Certa começou como uma iniciativa para gerar indicadores de glosas. A partir de uma provocação da Direção sobre o papel estratégico da TI, ampliei a leitura do problema: não bastava medir a perda no fim do processo; precisávamos integrar o ciclo que produz, documenta, recebe e recupera a receita.”


“A glosa era o sintoma. O problema real era a fragmentação do ciclo da receita. A solução foi desenhada em quatro frentes: visão fim a fim, automação crítica, gestão por evidência e governança operacional. Esse é o ponto central: TI atuando como alavanca de resultado e continuidade.”

## 3. Da demanda à visão sistêmica — 60 segundos

“A demanda inicial era legítima, mas localizada: indicadores. A mensagem da Direção mudou o enquadramento. Minha leitura foi que uma máquina de faturamento otimizada precisava de integração entre áreas, dados e decisões. Foi essa tradução de contexto em arquitetura que originou o Receita Certa como produto, e não como uma tela isolada.”

## 4. O cenário anterior — 55 segundos

“Cada etapa existia, mas as passagens eram frágeis. Produção no ERP, pedido de nota por e-mail ou planilha, emissão manual, controles separados de recebimento e histórico fragmentado de glosas. Isso gera retrabalho e atraso, mas o risco maior é financeiro: receita sem rastreabilidade, perda de prazo e gestão reativa.”

## 5. A solução integrada — 70 segundos

“O Receita Certa funciona como uma camada de integração. A interface organiza a experiência e os fluxos por perfil. A API concentra regras, dados, autenticação, conciliação e auditoria. A base hospitalar continua no MV/Oracle; o PostgreSQL registra o estado operacional; o Airflow executa a automação fiscal; e o portal do ISS é integrado ao fluxo. Recepção, financeiro, glosas e gestão passam a trabalhar sobre o mesmo ciclo.”

## 6. Quatro capacidades — 70 segundos

“A plataforma já foi construída em quatro blocos. Primeiro, faturamento e conciliação entre produção, nota fiscal, remessa e recebimento. Segundo, gestão completa de glosas, do follow-up ao recurso, acato e recuperação. Terceiro, inteligência gerencial para priorizar por valor, prazo, convênio e motivo. Quarto, automação fiscal, conectando o pedido das recepções à emissão e ao retorno da NFS-e.”

## 7. Automação de NFS-e — 75 segundos

“A indisponibilidade da rotina de emissão no ERP criou um risco concreto. O processo estava dependendo de e-mail, planilha e digitação manual. O Receita Certa digitaliza o pedido, permite a validação financeira e dispara a emissão. O robô executa a repetição, registra número, protocolo e PDF e devolve os erros para correção. A automação preserva a decisão humana: as pessoas validam e tratam exceções; a tecnologia executa o trabalho repetitivo.”

Pontos técnicos apenas se perguntados:

- A seleção do item é atômica para reduzir risco de emissão duplicada.
- O fluxo controla estados, lote, erro, protocolo e PDF.
- Itens com falha podem ser corrigidos e novamente processados.
- A solução suporta seleção da empresa emissora por CNPJ.

## 8. Indicadores — 65 segundos

“O painel foi desenhado para responder três perguntas: quanto está em risco, onde devemos agir e se a atuação está funcionando. Ele mostra totais glosados, não tratados, recursados, acatados, recuperados e em aberto. O funil evidencia conversão por convênio. O quadrante cruza impacto financeiro e eficiência de recuperação. Aging, Pareto e evolução mensal dão visão de prazo, causa e tendência.”

## 9. Evidência da ZeroGlosa — 70 segundos

“O estudo interno mostra R$ 104,4 mil de custo bruto em 17 meses. O fornecedor cobriu 15,4% da receita avaliada e 12,9% das contas. R$ 74 milhões ficaram fora do escopo. O ponto mais importante não é apenas o preço: o estudo não encontrou histórico integrado que permitisse atribuir ao fornecedor os recursos e valores recuperados. Portanto, a efetividade ainda precisa ser comprovada por evidência.”

## 10. Comparação de modelo — 70 segundos

“Não é uma comparação simples entre uma ferramenta externa e desenvolvimento interno. Os escopos são diferentes. A ZeroGlosa atua sobre uma parcela do problema; o Receita Certa integra o ciclo da receita e incorpora a automação fiscal. Ao mesmo tempo, precisamos manter rigor: não afirmo cobertura integral nem economia pronta. Para decidir corretamente, a organização precisa medir TCO interno, adoção e recuperação atribuível.”

## 11. Escala econômica — 65 segundos

“A escala mostra por que a visão sistêmica importa. Na base de R$ 74 milhões fora do fornecedor, uma variação de aproximadamente 0,14% equivale ao custo bruto acumulado de R$ 104,4 mil. Os cenários de 0,1%, 0,5% e 1% não são resultados realizados; servem para dimensionar a alavanca. E ainda existem ganhos não monetizados: redução de tempo, de horas manuais, de erros e de risco de continuidade.”

## 12. Implantação e agenda de valor — 70 segundos

“A solução tem base técnica concreta: três repositórios integrados, controle de acesso, trilhas de auditoria, estados de processo e 292 cenários de teste catalogados no código. O próximo passo é transformar capacidade em resultado medido. Em 90 dias, proponho fechar a linha de base, formalizar donos e SLAs, acompanhar o painel mensal e então comparar TCO interno e retorno atribuível para orientar a decisão contratual.”

## 13. Decisão executiva — 60 segundos

“Peço quatro direcionamentos: patrocinar o Receita Certa como plataforma corporativa do ciclo da receita; definir donos e SLAs entre as áreas; acompanhar o valor mensalmente; e reavaliar o fornecedor com base em cobertura e recuperação atribuível. A visão estratégica do projeto não foi automatizar uma tarefa. Foi criar disciplina institucional sobre a receita.”

## Respostas curtas para perguntas prováveis

### “Quanto o Receita Certa já economizou?”

“Ainda não é responsável afirmar um valor. Temos a capacidade implantada e cenários de escala; a proposta é fechar baseline e TCO para medir economia, recuperação e produtividade de forma atribuível.”

### “O sistema substitui a ZeroGlosa?”

“Funcionalmente, o Receita Certa cobre um escopo institucional mais amplo. A decisão de substituição deve ser econômica e operacional: recuperação atribuível, cobertura, qualidade, TCO e risco de continuidade.”

### “O Receita Certa cobre todos os convênios?”

“A arquitetura é multiconvênio e configurável. A cobertura real deve ser confirmada por dados, parametrização, rollout e adoção de cada área.”

### “Qual é o maior risco agora?”

“Ter tecnologia disponível sem padronizar o processo. Por isso, patrocínio, donos, SLAs e medição são tão importantes quanto o software.”

### “Por que TI liderou esse movimento?”

“Porque o problema atravessa áreas e sistemas. A TI teve a visão transversal necessária para conectar o fato gerador ao caixa, sem substituir a responsabilidade operacional de cada setor.”

## Atenção ao nome

A interface atual usa “Receita Certa”. O pedido inicial menciona “Receita Pronta”. Confirmar o nome institucional antes da reunião; se for “Receita Pronta”, substituir o nome na apresentação e no roteiro.
